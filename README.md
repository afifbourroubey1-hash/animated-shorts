# animated-shorts

خط إنتاج كامل ومفتوح المصدر لصناعة فيديوهات قصيرة عمودية (Shorts / Reels / TikTok) بأسلوب
**كرتون ثلاثي الأبعاد تعليمي**: شخصيات برؤوس دائرية وحدود سوداء، بيئات مشبعة الألوان، ترجمة كلمة بكلمة،
تعليق صوتي سريع، ونهاية تقطع على الذروة.

📘 **الدليل الكامل (بالعربية):** [`docs/GUIDE_AR.md`](docs/GUIDE_AR.md)

🎬 **النتيجة التجريبية:** [`docs/demo/`](docs/demo/)

## البدء السريع

```bash
pip install -r pipeline/requirements.txt          # numpy + bpy (Blender كمكتبة)

make timing-estimate EP=rail_gaps                 # أو: make voice (ElevenLabs) / make timing-audio WAV=my.wav
make captions audio EP=rail_gaps
make stills EP=rail_gaps                          # لقطة لكل مشهد للمراجعة
make preview video EP=rail_gaps                   # معاينة 15fps ثم MP4 في output/rail_gaps/
make final video EP=rail_gaps BLENDER=blender     # النهائي 1080x1920 على كرت الشاشة
```

## المراحل

| # | المرحلة | الملف |
|---|---|---|
| 1 | السكربت وقائمة اللقطات | `episodes/<id>/episode.json` |
| 2 | الصوت + توقيت الكلمات | `pipeline/tts_elevenlabs.py` · `pipeline/align_words.py` |
| 3 | بناء المشاهد وتحريكها وتصويرها | `pipeline/blender/build_episode.py` (+ `shots.py`, `characters.py`, `railroad.py` …) |
| 4 | الترجمة على الشاشة | `pipeline/make_captions.py` |
| 5 | المؤثرات + الموسيقى + المزج | `pipeline/make_audio.py` |
| 6 | التجميع والتصدير (−14 LUFS، H.264) | `pipeline/assemble.py` |

---

*English:* an end-to-end, code-driven pipeline (Python + Blender + FFmpeg) for 9:16 animated
explainer shorts: script → TTS with word timestamps → procedural 3D scenes, toon characters and
camera work → word-by-word pop captions → synthesized SFX/music with ducking → mastered MP4.
See `docs/GUIDE_AR.md` (Arabic) for the full walkthrough.
