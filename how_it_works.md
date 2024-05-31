# AlphaBI Sales Bot - How It Works - Overview

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
