# Use an official Ubuntu image as a parent image
FROM ubuntu:jammy

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Kolkata

# Update packages
RUN apt-get update && apt-get -y upgrade

# Update packages and install necessary dependencies
RUN apt-get install -y python3.10 python3-pip && apt-get clean

# Set the working directory in the container
WORKDIR /app

# Copy the requirements.txt file to the working directory
COPY requirements.txt .

# Install Python dependencies
RUN pip install -r requirements.txt

# Copy the rest of the application code to the container
COPY . .

# Expose the port specified in the environment variable
EXPOSE $PORT

# Command to run your Flask server
CMD ["python3", "app.py"]
