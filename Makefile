.PHONY: demo-text demo-image

OUTPUT_DIR ?= outputs
SAMPLE_IMAGE ?= outputs/sample.ppm


demo-text:
	python video_maker.py "cinematic aerial shot of a neon city" --duration 6 --fps 16 --output-dir $(OUTPUT_DIR)


demo-image:
	python scripts/make_sample_ppm.py $(SAMPLE_IMAGE)
	python video_maker.py --image $(SAMPLE_IMAGE) --duration 4 --fps 12 --output-dir $(OUTPUT_DIR)
