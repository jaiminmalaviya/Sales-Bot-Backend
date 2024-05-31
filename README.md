# AlphaBI-Sales-bot-API

## How It Works

1. **User Management**:

   - Users are authenticated based on their assigned roles (MEMBER or ADMIN) upon login.
   - Admin users can access the users section to add new member users.
   - Newly added users will receive login credentials and can access the system.

2. **Client Management**:

   - Users can navigate to the Accounts page to add new clients.
   - After providing basic client information, upon saving, an account is created for the client.

3. **Contact and Page Management**:

   - Users can add related contacts to an account as well as client website's pages(about us, services, home etc.) for each client from the Edit button on the right side of the row of the accounts table.
   - LinkedIn URLs are provided for contacts along with the name.
   - The contacts and the pages will be scraped, embedded and then stored in the pinecone db for helping in generation of ice breaker message.
   - Along with this things tha data like contacts, pages and basic account information will also be stored in the mongodb

4. **CRM Integration**:

   - we will use a change stream on the mongodb collection to keep an eye on them.
   - When we add, update any thing in the database we will also perform the changes in the fresh sales crm accordingly.

5. **Case Studies**:

   - Case studies can be accessed and added through the case studies section.
   - Markdown files with case study content and keywords are stored in mongoDB.
   - The .md files are embedded and stored in the pinecone database for getting AlphaBI's previous work experience that will help in generating the ice breaker message

6. **Industry and Icebreaker Generation**:
   - The system utilizes pinecone stored client website's web page embeddings to determine the industry of the client.
   - Icebreaker messages are generated using client industry data, contact LinkedIn profiles and case studies for previous work experience .

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
