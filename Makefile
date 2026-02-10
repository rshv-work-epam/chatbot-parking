.PHONY: test ci

test:
	pytest -q

ci: test
