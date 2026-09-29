format:
	prettier --write .

format:check:
	prettier --check .

lint:
	eslint .

typecheck:
	tsc --noEmit

test:
	vitest run

check:
	prettier --check . && tsc --noEmit && vitest run

security:
	npm audit --audit-level=high
