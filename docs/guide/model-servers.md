# Summary models and servers

Transcription and speaker identification run inside Voxtrama. The recap
and the extractions (decisions, themes, concepts) are written by a
**summary model** served by [Ollama](https://ollama.com). Without one,
jobs still produce the transcript and stop there.

## Ollama on the same machine

1. Install Ollama from [ollama.com](https://ollama.com) and start it.
2. Pull a model, for example:

    ```bash
    ollama pull qwen3:4b
    ```

3. In Voxtrama open **Settings**, then **Restart setup**, and go to
   **Model ready**. Voxtrama looks for Ollama at `localhost:11434`, lists
   the models it has, and you pick one. Or choose it later under
   **Settings › Change generative model**.

![Model ready: Ollama found, with its models](images/model-ready.png)

Ollama runs outside Docker, directly on your machine. That is what lets
it use the graphics chip of an Apple Silicon Mac. From inside the
containers, Voxtrama reaches it at `host.docker.internal:11434`.

## Ollama at another address

Set the address, and the model, in `.env`, then restart with
`make down` and `make up`:

```bash
VOXTRAMA_OLLAMA_URL=http://gpu-box.lan:11434
VOXTRAMA_OLLAMA_MODEL=qwen3:30b
```

If the server asks for credentials, add `VOXTRAMA_OLLAMA_AUTH`: a value
with a colon (`user:password`) is sent as Basic authentication, anything
else as a Bearer token. The credential never appears in logs or in a
job's record.

## Several servers

A job can choose among several model servers. Name them in `.env` as
JSON, each with its address and, if needed, its credential:

```bash
VOXTRAMA_PROVIDERS='{"default": {"url": "http://host.docker.internal:11434"}, "gpu": {"url": "http://gpu-box.lan:11434", "auth": "user:password"}}'
```

- The one called `default` is used unless a job chooses another; without
  a `default`, the first one is.
- The new-job form then shows **Model server**, each marked local or
  remote.
- Names use letters, digits, `.`, `_` and `-`, up to 64 characters.
- `VOXTRAMA_PROVIDERS` replaces `VOXTRAMA_OLLAMA_URL` when both are set.

### Local and remote

A server is **local** when its address is `localhost`, `127.0.0.1`,
`::1` or `host.docker.internal`, and **remote** otherwise. A job on a
remote server sends it the transcript and the context.

Steps marked `local_only` never go to a remote server: such a job is
refused before anything is sent. **Settings › Data & privacy** shows, for
each workflow, what would leave the machine.

## Which model

The summary model decides both the quality of the recap and how long it
takes. Some guidance:

- **Memory**: a model needs roughly its download size in memory, on top
  of what transcription uses. Voxtrama warns on the Model ready page when
  the machine looks short.
- **Speed**: on a processor, a model of a few billion parameters writes a
  few words per second, so a long recap takes minutes. The same model on
  a graphics card is many times faster. If your machine has no usable
  graphics chip, pointing Voxtrama at an Ollama server on a machine that
  has one is the biggest speed-up available.
- **Size**: small models follow the instructions less closely. They write
  fewer points than asked, or quotes that cannot be found in the
  transcript, which then show as **Needs review**.

Ollama on an Intel Mac runs on the processor only, even when the Mac has
a graphics card.

## Context window

A long transcript can exceed what the model reads at once. Voxtrama reads
the model's limit from Ollama, splits a long transcript into parts of
about 12,000 characters, and joins the results. Under
**Settings › Change generative model**, **Use at most** lowers the limit
Voxtrama uses. A lower limit costs time (more parts), not completeness.

Voxtrama sends two parts to the model at the same time, and the step
waits for the slowest instead of adding them up.
`VOXTRAMA_PARALLEL_WINDOWS` in `.env` changes the number; `1` sends them
one after another. Ollama answers them together only when it was started
with `OLLAMA_NUM_PARALLEL` at least as high, and it reserves the context
memory once per parallel request, so a machine short of memory is better
off with `1`. The Activity panel shows each part as it is sent and as it
is answered, in whatever order the answers arrive.

## Time limit

A single call to the summary model may take up to 30 minutes before the
step fails with a timeout. `VOXTRAMA_PROVIDER_TIMEOUT_SECONDS` in `.env`
changes this limit.
