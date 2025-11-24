# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Health check - verifies Python is working and can import basic modules
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import sys, os; sys.exit(0 if os.path.exists('/app/tracker.py') else 1)"

# Run tracker.py when the container launches
CMD ["python", "tracker.py"]
