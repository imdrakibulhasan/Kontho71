# Kontho API reference

Base URL: your server, e.g. `http://localhost:8000`. Interactive OpenAPI docs: `/docs`.

**Authentication** (only when `KONTHO_AUTH=true`): send `xi-api-key: <key>` or `Authorization: Bearer <key>`.
Create keys in *Settings & API* or with `POST /v1/api-keys` (using `KONTHO_ADMIN_KEY` for the first one).

Errors use the ElevenLabs shape: `{"detail": {"status": "...", "message": "..."}}`, with status 401, 404, 422 (bad input) or 503 (engine not installed).

Endpoints marked ★ are Kontho extensions; all others mirror the ElevenLabs API.

## Text to speech
| Method | Path | Notes |
|---|---|---|
| POST | `/v1/text-to-speech/{voice_id}` | JSON `{text, model_id, language_code, voice_settings{stability, similarity_boost, speed}, seed, emotion ★}`; query `output_format` (e.g. `mp3_44100_128`, `wav_24000`, `pcm_16000`, `opus_48000_64`, `flac_44100`, `ulaw_8000`). Response audio has the `history-item-id` header |
| POST | `/v1/text-to-speech/{voice_id}/stream` | Chunked audio, sentence by sentence |
| POST | `/v1/text-to-speech/{voice_id}/with-timestamps` | `{audio_base64, alignment{characters, character_start_times_seconds, character_end_times_seconds}}` (timings are approximate per character) |

## Voices
| Method | Path | Notes |
|---|---|---|
| GET | `/v1/voices`, `/v2/voices` | `?search=&category=premade\|cloned\|designed` |
| GET | `/v1/voices/{voice_id}` | |
| GET | `/v1/voices/{voice_id}/preview` ★ | WAV preview, generated on first request |
| POST | `/v1/voices/add` | multipart: `name`, `files[]`, `description`, `labels` (JSON), `remove_background_noise`, `reference_text` ★, `language` ★ |
| POST | `/v1/voices/{voice_id}/edit` | multipart: `name`, `description`, `labels`, `reference_text` |
| DELETE | `/v1/voices/{voice_id}` | Premade voices cannot be deleted |
| GET | `/v1/voices/settings/default` | |

## Emotions ★
| Method | Path | Notes |
|---|---|---|
| GET | `/v1/emotions` | Emotion vocabulary with Bengali names and aliases |
| GET | `/v1/voices/{voice_id}/emotions` | The voice's emotion clips |
| POST | `/v1/voices/{voice_id}/emotions` | multipart: `emotion`, `files[]`, `reference_text`, `remove_background_noise`, `language`. Replaces an existing clip for that emotion |
| GET | `/v1/voices/{voice_id}/emotions/{emotion}/audio` | The clip (WAV) |
| DELETE | `/v1/voices/{voice_id}/emotions/{emotion}` | |
| POST | `/v1/voices/import-pack` | multipart `file` (.zip of `voice_emotion.mp3` + optional `transcripts.txt`), `language`. Creates or updates one voice per prefix |

In text-to-speech, write `[emotion]` tags in `text` (or set `"emotion"` in the body as the default). The `emotions-used` response header reports `requested=used` pairs.

## Voice design
| Method | Path | Notes |
|---|---|---|
| GET | `/v1/text-to-voice/options` ★ | Supported attributes (gender, age, pitch, accent, style) |
| POST | `/v1/text-to-voice/create-previews` (alias `/design`) | `{voice_description, text?, language?, seed?}` → 3 previews with `generated_voice_id` + `audio_base_64`. Free-form descriptions are mapped to supported attributes ("old man, deep voice" → `male, elderly, low pitch`); unknown words are listed in `ignored_terms` |
| POST | `/v1/text-to-voice/create-voice-from-preview` (alias `/v1/text-to-voice`) | `{voice_name, generated_voice_id, voice_description?, labels?}` |

## Speech to text
| Method | Path | Notes |
|---|---|---|
| POST | `/v1/speech-to-text` | multipart: `file`, `language_code`, `diarize`, `num_speakers`; query `format=json\|srt\|vtt\|txt` ★. JSON includes `words[]` (with `speaker_id`) and `segments[]` ★ |

## Voice changer, sound effects, isolation
| Method | Path | Notes |
|---|---|---|
| POST | `/v1/speech-to-speech/{voice_id}` (+`/stream`) | multipart: `audio`, `model_id`, `voice_settings` (JSON), `remove_background_noise`, `keep_background` ★, `seed` |
| POST | `/v1/sound-generation` | `{text, duration_seconds (0.5–30), prompt_influence (0–1), seed}` |
| POST | `/v1/audio-isolation` (+`/stream`) | multipart `audio`; query `stem=vocals\|background` ★ |

## Dubbing
| Method | Path | Notes |
|---|---|---|
| POST | `/v1/dubbing` | multipart: `file`, `target_lang`, `source_lang` (`auto`), `num_speakers` (0 = auto), `name`, `voice_id` ★ (use one library voice instead of cloning), `drop_background_audio` |
| GET | `/v1/dubbing` | List projects |
| GET | `/v1/dubbing/{id}` | `status`: `dubbing` → `dubbed` / `failed`, plus `progress` and `message` ★ |
| GET | `/v1/dubbing/{id}/audio/{lang}` | MP4 for videos, MP3 for audio; `?kind=audio` ★ always returns MP3 |
| GET | `/v1/dubbing/{id}/transcript/{lang}` | `?format_type=srt\|webvtt`; use the source language for the original transcript |
| GET | `/v1/dubbing/{id}/segments` ★ | Editable segments (text, translation, speaker, timing, voice) |
| PATCH | `/v1/dubbing/{id}/segments/{index}` ★ | `{translation?, text?, start?, end?, speaker?, voice_id?, retranslate?}` marks the segment dirty |
| POST | `/v1/dubbing/{id}/render` ★ | Re-voice dirty segments and rebuild the outputs |
| DELETE | `/v1/dubbing/{id}` | |

## History, account, system
| Method | Path | Notes |
|---|---|---|
| GET | `/v1/history` | `?page_size=&start_after_history_item_id=&kind=tts\|sts\|sfx\|isolation\|stt&voice_id=` |
| GET / DELETE | `/v1/history/{id}` | |
| GET | `/v1/history/{id}/audio` | Original WAV, or `?output_format=` to convert |
| GET / POST / DELETE | `/v1/pronunciation[/{id}]` ★ | `{term, replacement, language}` |
| GET | `/v1/models`, `/v1/languages` ★ | |
| GET | `/v1/user`, `/v1/user/subscription` | Self-hosted: unlimited |
| GET | `/v1/system/status` ★ | Engines, device, ffmpeg |
| GET / POST / DELETE | `/v1/api-keys[/{id}]` ★ | The raw key is returned once on creation |
