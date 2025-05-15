# Use a slim Python 3.11 base image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy the entire project into the container
COPY . .

# Upgrade pip and install dependencies
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Expose the port Chainlit runs on
EXPOSE 8000

# Run the Chainlit app
CMD ["chainlit", "run", "app.py", "--port", "8000", "--host", "0.0.0.0"]
