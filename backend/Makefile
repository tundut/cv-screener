build-CvProcessorFunction:
	# Install runtime dependencies (boto3 ships in the Lambda runtime; PyPDF2 does not).
	python -m pip install --no-cache-dir PyPDF2 -t "$(ARTIFACTS_DIR)"
	# Copy the backend Python modules.
	cp $(CURDIR)/*.py "$(ARTIFACTS_DIR)"
	# Copy the prompt template (lives inside backend/, within CodeUri).
	mkdir -p "$(ARTIFACTS_DIR)/prompts"
	cp $(CURDIR)/prompts/cv_evaluation.txt "$(ARTIFACTS_DIR)/prompts/"
