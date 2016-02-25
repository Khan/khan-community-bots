.PHONY: lint linc serve deploy

lint linc:
	../devtools/khan-linter/runlint.py .

serve:
	dev_args="--host ::1"
	if command -v technicolor-yawn >/dev/null 2>&1; then \
		dev_appserver.py $$dev_args ./app.yaml 2>&1 | technicolor-yawn; \
	else \
		dev_appserver.py $$dev_args ./app.yaml; \
	fi

deploy:
	appcfg.py -A khan-community-bots update app.yaml
