# Get Started with AlphaBI Sales Bot

Welcome to AlphaBI Sales Bot! This guide provides step-by-step instructions to set up the development environment for the project and get started with running the server.

## 1. Clone the Project Repository

To get started, clone the AlphaBI Sales Bot project repository from GitHub using the following command:

```sh
git clone https://github.com/RshmanGit/AlphaBI-Sales-bot-API.git
```

## 2. Set Up Development Environment

### Create a Virtual Environment (Optional but Recommended)

It's a good practice to work within a virtual environment to isolate project dependencies. Create a virtual environment using the following command:

```sh
python -m venv env
```

Activate the virtual environment:

- **For Windows**:

  ```sh
  env\Scripts\activate
  ```

- **For macOS/Linux**:

  ```sh
  source env/bin/activate
  ```

### Install Dependencies

Navigate to the project directory and install Python dependencies using pip:

```sh
cd sales-bot
pip install -r requirements.txt
```

## 3. Configure Database

AlphaBI Sales Bot requires a database to store data. Obtain the necessary database configuration from the `.env` file in the sales bot's documents section in the open project. Copy the contents of the `.env` file to a new `.env` file in the project directory.


## 4. Run the Server

Start the Flask server by running the following command:

```sh
python app.py
```



By following these steps, you'll have the AlphaBI Sales Bot project set up locally on your machine, ready for development and testing.Happy coding!
```



