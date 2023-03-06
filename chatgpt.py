"""A ChatGPT TUI interface using Textual."""

import asyncio
import dataclasses
import json
import uuid
from dataclasses import dataclass
from pathlib import Path

import openai
from textual.app import App
from textual.containers import Container, Vertical
from textual.reactive import var
from textual.widgets import Footer, Input, Label, ListItem, ListView, Markdown, Static


@dataclass(slots=True)
class Session:
    """A class to represent a session."""

    uuid: str
    title: str
    prompts: list[dict[str, str]]


class ChatGPT(App):
    """A Textual App to interface with ChatGPT.

    Attributes:
        show_sessions_history: A flag to determine if the sessions history should be shown.
        current_session: A Session object representing the current session.
        last_request: A Task representing the last request to ChatGPT.
    """

    SESSIONS_DIR = Path.home() / ".cache" / "chatgpt-tui"
    CSS_PATH = "style.css"
    BINDINGS = [
        ("ctrl+t", "sessions_history", "Toggle sessions history list"),
        ("ctrl+n", "new_session", "Start a new session"),
    ]

    show_sessions_history = var(default=False)
    background_task: set[asyncio.Task] = set()
    last_request: asyncio.Task = None
    current_session: Session = None
    sessions: list[Session] = []

    def watch_show_sessions_history(self, value: bool) -> None:  # noqa: FBT001
        """A callback that will run when the show_sessions_history flag changes.

        Args:
            value: The new value of the flag.
        """
        self.set_class(value, "-show-sessions-history")

    def action_sessions_history(self) -> None:
        """A callback that will run when the sessions_history action is triggered."""
        self.show_sessions_history = not self.show_sessions_history

    def action_new_session(self) -> None:
        """A callback that will run when the new_session action is triggered."""
        self.current_session = None
        task = asyncio.create_task(self.reset_chat_history())
        self.background_task.add(task)
        task.add_done_callback(self.background_task.discard)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """A callback that will run when a session is selected in the sessions history list.

        Args:
            event: A ListView.Selected event.
        """
        self.current_session = self.sessions[self.sessions_history.index]
        task = asyncio.create_task(self.reset_chat_history())
        self.background_task.add(task)
        task.add_done_callback(self.background_task.discard)

    async def reset_chat_history(self) -> None:
        """Reset the chat history to the current session."""
        await self.chat_history.query(Static).remove()
        await self.chat_history.query(Markdown).remove()
        if self.current_session:
            for prompt in self.current_session.prompts:
                await self.chat_history.mount(
                    Static(prompt["question"], classes="user-prompt"),
                )
                await self.chat_history.mount(Markdown(prompt["answer"]))
            self.call_after_refresh(self.chat_history.scroll_end, animate=False)

    async def save_session(self, session: Session) -> None:
        """Save a session to the sessions directory.

        Args:
            session: Session to save.
        """
        # Make sure the sessions dir exists
        self.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        with self.SESSIONS_DIR.joinpath(session.uuid + ".json").open("w") as f:
            json.dump(dataclasses.asdict(session), f, indent=4)

    from collections.abc import AsyncIterable

    from textual.widget import Widget

    def compose(self) -> AsyncIterable[Widget]:
        """Yield widgets to compose the app."""
        # Get all files in the sessions dir and remove the extension to get the uuid then load the session
        if self.SESSIONS_DIR.exists():
            sessions = sorted(
                self.SESSIONS_DIR.iterdir(),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            for session in sessions:
                with session.open() as f:
                    self.sessions.append(Session(**json.load(f)))
        with Container():
            yield ListView(
                *[ListItem(Label(session.title)) for session in self.sessions],
                id="sessions-history",
            )
            yield Vertical(id="chat-history")
        yield Input(id="chatgpt-query")
        yield Footer()

    def on_mount(self) -> None:
        """A callback that will run when the app is mounted."""
        self.query_one(Input).focus()

    @property
    def chat_history(self) -> Vertical:
        """A getter for the chat history container.

        Returns:
            The chat history container.
        """
        return self.query_one("#chat-history", Vertical)

    @property
    def sessions_history(self) -> ListView:
        """A getter for the sessions history list.

        Returns:
            The sessions history list.
        """
        return self.query_one("#sessions-history", ListView)

    async def send_chatgpt_request(self, prompt: str) -> None:
        """Send a request to ChatGPT using openai's API.

        Args:
            prompt: The new prompt to send to ChatGPT.
        """
        if not self.current_session:
            # TODO: Better title, maybe use chatgpt to generate it? {"role": "system", "content": "...."}
            self.current_session = Session(
                uuid=str(uuid.uuid4()),
                title=prompt,
                prompts=[],
            )
        messages = [
            {"role": "user", "content": prompt["answer"]}
            for prompt in self.current_session.prompts
        ] + [{"role": "user", "content": prompt}]
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.5,
        )
        answer = response.choices[0]["message"]["content"]
        await self.chat_history.mount(
            Markdown(answer),
        )
        self.call_after_refresh(self.chat_history.scroll_end, animate=False)
        self.current_session.prompts.append(
            {"question": prompt, "answer": answer},
        )
        await self.save_session(self.current_session)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Callback that will run when the user submits a question.

        Args:
            event: An Input.Submitted event.
        """
        if event.value == "":
            return
        if self.last_request and not self.last_request.done():
            return

        self.chat_history.mount(Static(event.value, classes="user-prompt"))
        self.query_one(Input).value = ""
        self.last_request = asyncio.create_task(
            self.send_chatgpt_request(event.value),
        )


if __name__ == "__main__":
    ChatGPT().run()
