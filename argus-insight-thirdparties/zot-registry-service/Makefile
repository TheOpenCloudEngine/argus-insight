ZOT_URL := https://github.com/project-zot/zot/releases/latest/download/zot-linux-amd64
IMAGE_NAME := argus-zot

.PHONY: build clean

build: zot
	docker build -t $(IMAGE_NAME) .

zot:
	curl -Lo zot $(ZOT_URL)
	chmod +x zot

clean:
	rm -f zot
