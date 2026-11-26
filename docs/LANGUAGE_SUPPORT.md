# Welsh and English language support

Orinoco should treat Welsh and English as first-class languages. The language setting controls reply style; it does not change account identity, privacy boundaries, memory ownership, tool permissions or the local-only inference architecture.

## User setting

Account settings → Response preferences → Reply language:

- `auto` (default): reply in the language of the latest user message.
- `en`: prefer English.
- `cy`: prefer natural Welsh (Cymraeg).

A direct request to answer in another language may override the saved preference for that reply. Preserve Welsh spelling and diacritics. Do not translate unless asked. If a user code-switches, follow the predominant or latest language naturally.

## Local model evaluation

Do not assume that a model is bilingual because its model card says multilingual or because it follows one prompt. Run this benchmark with the exact local Ollama model tag, context length and resource limits intended for release. No external inference provider may be used.

### Capture model responses

From the Orinoco repository on the machine running Ollama, run:

```bash
python scripts/benchmark_languages.py --model qwen2.5:1.5b --context 4096
```

Replace the model tag with the exact model selected for the test. The script sends the paired prompt set to the local Ollama loopback API, includes prior user/assistant turns for the follow-up test, writes a timestamped JSON report, and does not call an external inference service. It is a **model-only baseline** using a compact Orinoco language instruction; it does not exercise the full application, account preference setting, conversation history, or UI. Keep the generated report local unless you have checked it for private content.

For application-level acceptance, also complete the preference and switching checks below against the running Orinoco UI/API. Record the actual model tag, Ollama version, context and hardware in the report table.

Record:

| Field | Value |
|---|---|
| Model tag and digest (if available) | Pending |
| Ollama version | Pending |
| Context length | Pending |
| VPS CPU / RAM | Pending |
| Test date | Pending |
| Welsh score | Pending |
| English score | Pending |
| Code-switch score | Pending |
| Notes / failure examples | Pending |

### Prompt set

Use the same intent in both languages and record the model's actual output.

| Skill | English prompt | Welsh prompt |
|---|---|---|
| Greeting | Hello, what can you help me with? | Helo, beth allwch chi fy helpu i ag ef? |
| Explanation | Explain why the sky looks blue in simple terms. | Eglurwch pam mae'r awyr yn edrych yn las mewn termau syml. |
| Practical steps | Give me three steps to make a cup of tea. | Rhowch dri cham i mi wneud paned o de. |
| Summary | Summarise this short paragraph in two sentences: [use the same paragraph]. | Crynhowch y paragraff byr hwn mewn dwy frawddeg: [use the same paragraph]. |
| Follow-up | Now make that explanation shorter. | Nawr gwnewch yr eglurhad hwnnw'n fyrrach. |
| Welsh names / diacritics | Include the names Ceredigion, Llŷr and Siân correctly. | Defnyddiwch yr enwau Ceredigion, Llŷr a Siân yn gywir. |

### Preference and switching checks

1. In automatic mode, send the English prompts and confirm replies are in English.
2. Send the Welsh prompts and confirm replies are in Welsh.
3. In one conversation, switch Welsh → English → Welsh and check that the assistant follows without losing context.
4. Set English preference and send a Welsh message; expect English unless the message explicitly asks for Welsh for that reply.
5. Set Welsh preference and send an English message; expect Welsh unless the message explicitly asks for English for that reply.
6. Issue a one-turn language request and verify the saved setting remains unchanged.
7. Test an ordinary mixed-language message and ensure Orinoco does not translate the whole conversation unnecessarily.

### Scoring

Score each response from 0 to 2 for each applicable item:

- **Meaning:** correctly understands the request and any follow-up.
- **Language:** uses the expected language and does not drift unnecessarily.
- **Quality:** natural grammar, readable phrasing and correct Welsh diacritics.
- **Accuracy:** factual content is correct and uncertainty is handled honestly.
- **Instruction following:** obeys requested length, format and language preference.

Suggested release gate: at least 80% of available points in each language, no critical factual or privacy failure, and no repeated language-selection failure. Treat this as a project acceptance threshold, not a guarantee of native-level fluency. Record weak examples and compare a larger model only if the VPS resource budget allows.

## Memory and privacy

- Memory is owned by the account, not by the language.
- Switching language must not create a separate memory store or expose another account's memory.
- Model-generated memory candidates must be checked for sensitive information written in Welsh as well as English.
- Keep the local sensitive-term filter as a second layer; it is not a complete Welsh-language privacy classifier.
- Test both rejection of sensitive Welsh facts and retention of harmless Welsh preferences.

## Voice (future work)

Voice is not implemented yet. When it is, evaluate local speech recognition and speech output separately for Welsh and English, including pronunciation, Welsh diacritics/names, language preference and code-switching. Do not mark voice criteria complete until the actual local components have been tested.
