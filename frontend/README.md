# Frontend: Speech Transcribe Demo

Минимальное frontend-приложение для записи голоса через `MediaRecorder` и отправки аудио на backend endpoint `POST /speech/transcribe`.

## Запуск

```bash
python -m http.server 5173 --directory frontend
```

Откройте `http://127.0.0.1:5173`.

> Для разработки удобно запускать backend на `http://127.0.0.1:8000` и проксировать `/speech/transcribe` через dev-сервер, либо отдавать frontend тем же origin.

## Контракт ответа

Ожидаемый JSON от backend:

```json
{
  "text": "string",
  "language": "string",
  "provider": "string"
}
```

UI-состояния:
- `idle`
- `recording`
- `uploading`
- `transcribed`
- `error`
