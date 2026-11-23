# Animated Shorts pipeline — see docs/GUIDE_AR.md
EP ?= rail_gaps
PY ?= python3
BLENDER ?=            # set to "blender" to render with the Blender app (GPU)

.PHONY: all voice timing-estimate timing-audio captions audio stills preview final video clean

all: captions audio preview video

voice:              ## ElevenLabs TTS + exact word timings (needs ELEVENLABS_API_KEY)
	$(PY) pipeline/tts_elevenlabs.py $(EP)

timing-estimate:    ## no voice yet: estimated timings for the animatic
	$(PY) pipeline/align_words.py $(EP) --estimate

timing-audio:       ## your own recording: make timing-audio WAV=my_voice.wav
	$(PY) pipeline/align_words.py $(EP) --audio $(WAV)

captions:
	$(PY) pipeline/make_captions.py $(EP)

audio:
	$(PY) pipeline/make_audio.py $(EP)

stills:             ## one frame per shot -> output/$(EP)/stills
	$(PY) pipeline/blender/build_episode.py $(EP) --preview --stills

preview:            ## 15 fps low-res animatic (CPU friendly)
	$(PY) pipeline/blender/build_episode.py $(EP) --preview --samples 8 --step 2

final:              ## 1080x1920, 30 fps (use a GPU: make final BLENDER=blender)
ifeq ($(strip $(BLENDER)),)
	$(PY) pipeline/blender/build_episode.py $(EP) --final
else
	$(BLENDER) -b -P pipeline/blender/build_episode.py -- $(EP) --final
endif

video:              ## assemble frames + mix + captions -> output/$(EP)/$(EP).mp4
	$(PY) pipeline/assemble.py $(EP)

clean:
	rm -rf output/$(EP)/frames output/$(EP)/stills
