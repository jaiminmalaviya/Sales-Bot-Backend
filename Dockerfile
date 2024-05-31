# Use an official Ubuntu image as a parent image
FROM amd64/ubuntu:latest

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set timezone
ENV TZ=Asia/Kolkata

# Update packages and install necessary dependencies
RUN apt-get update && \
    apt-get install -y python3.10 python3-pip chromium-browser chromium-driver && \
    apt-get clean

# Set the working directory in the container
WORKDIR /app

# Copy the requirements.txt file to the working directory
COPY requirements.txt .

# Install Python dependencies
RUN pip install --break-system-packages -r requirements.txt
RUN playwright install
RUN playwright install-deps
RUN apt-get install -y wget
RUN apt install chromium-browser

RUN apt-get install -y wget
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN apt-get install -y ./google-chrome-stable_current_amd64.deb


# Copy the rest of the application code to the container
COPY . .

# Expose the port specified in the environment variable
EXPOSE $PORT

# Command to run your Flask server
CMD ["python3", "app.py"]
