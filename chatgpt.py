import openai

from pathlib import Path
import asyncio
import json
import uuid

from textual.app import App
from textual.containers import Container, Vertical
from textual.reactive import var
from textual.widgets import (
    Input,
    Markdown,
    Label,
    Static,
    ListView,
    DirectoryTree,
    ListItem,
)

from dataclasses import dataclass
import dataclasses


@dataclass(slots=True)
class Session:
    uuid: str
    title: str
    prompts: list[dict[str, str]]


class ChatGPT(App):
    SESSIONS_DIR = Path.home() / ".cache" / "chatgpt-tui"
    CSS_PATH = "style.css"
    BINDINGS = [
        ("ctrl+t", "sessions_history", "TODO"),
    ]

    show_sessions_history = var(default=False)
    background_task: set[asyncio.Task] = set()
    last_request: asyncio.Task = None
    current_session: Session = None
    sessions: list[Session] = []

    def watch_show_sessions_history(self, value: bool) -> None:
        self.set_class(value, "-show-sessions-history")

    def action_sessions_history(self):
        self.show_sessions_history = not self.show_sessions_history

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.current_session = self.sessions[self.sessions_history.index]
        task = asyncio.create_task(self.reset_chat_history())
        self.background_task.add(task)
        task.add_done_callback(self.background_task.discard)

    async def reset_chat_history(self):
        await self.chat_history.query(Static).remove()
        await self.chat_history.query(Markdown).remove()
        for prompt in self.current_session.prompts:
            await self.chat_history.mount(
                Static(prompt["question"], classes="user-prompt"),
            )
            await self.chat_history.mount(Markdown(prompt["answer"]))
        self.call_after_refresh(self.chat_history.scroll_end, animate=False)

    async def save_session(self, session: Session):
        # Make sure the sessions dir exists
        self.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        with self.SESSIONS_DIR.joinpath(session.uuid + ".json").open("w") as f:
            json.dump(dataclasses.asdict(session), f, indent=4)

    def update_sessions_history(self):
        pass

    def compose(self):
        # Get all files in the sessions dir and remove the extension to get the uuid then load the session
        if self.SESSIONS_DIR.exists():
            for session in self.SESSIONS_DIR.iterdir():
                with session.open() as f:
                    self.sessions.append(Session(**json.load(f)))
        with Container():
            yield ListView(
                *[ListItem(Label(session.title)) for session in self.sessions],
                id="sessions-history",
            )
            yield Vertical(id="chat-history")
        yield Input(id="chatgpt-query")

    def on_mount(self):
        self.query_one(Input).focus()

    @property
    def chat_history(self) -> Vertical:
        return self.query_one("#chat-history", Vertical)

    @property
    def sessions_history(self):
        return self.query_one("#sessions-history", ListView)

    async def send_chatgpt_request(self, prompt: str):
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
