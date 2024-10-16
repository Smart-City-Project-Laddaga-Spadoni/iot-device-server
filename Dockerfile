# Use a base Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the requirements.txt file and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Copy the AWS credentials file to the correct path
COPY ~/.aws/credentials /root/.aws/credentials

# Export environment variables
ENV FLASK_APP=application.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000
ENV JWT_ACCESS_TOKEN_EXPIRES=3600
ENV MONGODB_DBNAME=SmartCityDB

# Expose the port for Flask
EXPOSE 5000

# Command to start the application
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]