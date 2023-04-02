# ChatGPT-tui

[![Format](https://github.com/JafarAbdi/chatgpt-tui/actions/workflows/format.yml/badge.svg)](https://github.com/JafarAbdi/chatgpt-tui/actions/workflows/format.yml)

A terminal user interface for [ChatGPT API](https://openai.com/blog/introducing-chatgpt-and-whisper-apis#chat-gpt-api)
using [textual](https://github.com/Textualize/textual)

[![Demo]](https://user-images.githubusercontent.com/16278108/222926204-ee07e55e-5058-4238-b960-38c902433e65.mp4)

## Installation

Assuming you have [micromamba](https://mamba.readthedocs.io/en/latest/installation.html#automatic-installation)

```bash
micromamba create -f environment.yml
```

## Usage

- Set `OPENAI_API_KEY` environment variable. which you can be generated from [api-keys](https://platform.openai.com/account/api-keys)

- `micromamba run -n chatgpt python3 chatgpt.py`
