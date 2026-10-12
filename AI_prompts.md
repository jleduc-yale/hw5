# AI Prompts Log

## Problem 1: Vibe coder prompts

### Prompt 1

```
Problem 1:

In the HW 5 folder, create an AI_prompts.md file. This file will contain a running log of the prompts I give to you over the course of finishing this homework. Every time I give you a prompt you need to record it in that file word for word under the appropriate problem section. For example, this prompt should go under "Problem 1: Vibe coder prompts".
```

## Problem 2: Study the Campus Customs database

### Prompt 1

```
For “Problem 2: Study the Campus Customs database”, examine and research the data/campus_customs.db file. Copy that file to a new file data/campus_customs_new.db. Later problems only update the new file we created. When you are studying the DB file make sure to look at how the open tickets relate to the other tables in the file. Create an output/harness.md file that enumerates all the fields in all the tables (organized by table, of course) and has a short description of why that table matters for our agents that we will be implementing. This harness.md file we be appended to later on in future problems.
```

## Problem 3: Build the MCP server

### Prompt 1

```
For “Problem 3: Build the MCP server”, create an MCP server in the mcp_server/ folder using FastMCP. It will interact with the data/campus_customs_new.db database. No need to run or connect the server just yet. All the agents we create in later problems will use this MCP server’s tools. As a start, add three tools that we need to complete the tickets in the database. Make sure the tool names are descriptive and understandable. Do not invent any data, make sure all data comes directly from the database. In output/harness.md describe the 3 MCP tools that you added. For each tool describe: what table it reads, which ticket it helps accomplish, and a sentence on why that specific tool is the correct one to use to complete the ticket. Create a mcp_server/README.md file that describes the MCP server, its main uses, the database it interacts with, and the tools it utilizes.
```

## Problem 4: Add the MCP server to vibe coder and test each tool

### Prompt 1

```
For “Problem 4: Add the MCP server to vibe coder and test each tool”, connect to the MCP server so you can call the tools yourself. That is I want this running Claude instance to be able to talk to the MCP server that we are creating. Save the resulting connection json in the .mcp.json how ever you save local MCP server lists (it may be at the project root, may not be). Then, with your connection to the MCP we just created, test each of the MCP tools and save the evidence that you tested them in output/mcp_smoke.json. Make sure that each tool test includes: the name of the tool, the prompt that you asked Claude, and the tool output. Keep in the mind the tool output must match values from the new DB file that we created.
```


## Problem 5: Build the agent team and grow the MCP tools

### Prompt 1

```
For “Problem 5: Build the agent team and grow the MCP tools”, create the agent team each using PydanticAI. There should be: Boss, Inventory, Accounting, Facilities, and Customer Service. Each agent should have their own prompt, model, and loop so that they can communicate and delegate work to each other with no gaps in connectivity. The agent prompts should be in backend/prompts/, data types should be in backend/models.py, and the agent files should live under backend/. Every agent should only use my PORTKEY_API_KEY and gpt-6-luna. Create each prompt for the agent with a description for the shop rules the agent needs. The prompts need to cover all aspects of the agents role and scope instead of just being short and vague. Add whatever tools the agents will need to the MCP server so that the agents can work directly with the MCP server to get data (they never try to invent a backway route to the new db file that bypasses the MCP). Every time the agents run make sure they append to the output/audit_trail.json file. For each loop step, record enough information so that we can audit what happens after a run. Make sure the audit_trail file is a running log of all agent activity and doesn’t get wiped after each run. Simply append information to the end. In output/harness.md, describe every agent and every MCP tool (include the ones just added) along with which table the tool interacts with. In addition, add a short safety section to the harness.md file that describes the safety features that an actual business would want when the agents are working with real data with real customer information and real money. Also add a description of how we would want to limit token usage to keep costs in check. Finally, update the mcp_server/README.md file by adding any tools you added in this problem to the file with the same structure as the existing tool descriptions.
```

## Problem 6: Plan the three tickets

### Prompt 1

```
For “Problem 6: Plan the three tickets”, create a output/desk_tickets.html file that has one tab per ticket. And two additional tabs called “Cash” and “Reflection” for later problems. The two additional tabs should be blank for now. Each ticket tab should have an “Expected” section with room for an “Actual” section later on that we will fill once the agents actually complete the tickets. In the expected section for each ticket, describe what you think the team of agents will do for each open ticket. Describe which agent you think the Boss agent should call first and give a reason why the boss would call that agent, describe all the agent delegations that you think will happen to solve the task, and which MCP tools that you expect those agents to use. Keep in mind that plans that use every agent aren’t efficient and shouldn’t be how the agent runs
```

## Problem 7: Backend routes

### Prompt 1

```
For “Problem 7: Backend routes”, create backend/main.py and make it use FastAPI and add routes that accomplish the following things: respond with all three tickets including information about their status (open or resolved), take a ticket id as an argument and return the agents that are on that ticket, respond with recent agent events (tools used and what the agents said) so that a frontend page can be up to date, approve a payment or purchase once a human confirms the payment/purchase, return the current balance of the checking account from cash_accounts, reset the DB to the initial DB so that we can do a fresh run. Once that is done, we should turn on the server with the following command: “uvicorn main:app --reload --port 8000”. In output/harness.md add a section describing each route, make sure to note the URL of the route and a short description of what it does.
```

## Problem 8: Agent dashboard

### Prompt 1

```
For “Problem 8: Agent dashboard”, create the frontend dashboard in frontend/. This dashboard should use React + Vite + TypeScript. This page should use the routes we created in the previous problem. The dashboard should: show all three tickets, let you select a ticket and begin the agent team working on it, show each agent and what they are saying and doing when they are working on the ticket, update the ticket to show it is resolved once the agents are finished, display a summary of what each agent did to complete a ticket, have functionality to let a human confirm payments and purchases when asked about it, it should also show the checking balance and the balance should update if things are paid for. While you are doing all this, make sure that the dashboard looks good and professional. Make sure the frontend knows to talk to the backend at localhost:8000. Make sure the backend allows the Vite page origin so the browser allows the calls. Make sure the board starts with “npm run dev”. Finally, create output/design.md describing the decisions you made for styling the dashboard. Include things like layout, how tickets show up and how they are differentiate visually once they are resolved, how cash shows up. Also include the why of the design decisions. Include the choices that make humans enjoy the website. Remember you can style (and should style) this dashboard however you want.
```

## Problem 9: Resolve the tickets

### Prompt 1

```
For “Problem 9: Resolve the tickets”, reset the data/campus_customs_new.db back to its original state so we start clean. Mark down the starting checking balance. Run all three tickets until the agents complete them all. Update the output/desk_tickets.html with the actual data from this run (this will go in the actual section for each of the tickets). Note down: which agents worked on the ticket, what they delegated to other agents, and which tools the agents used. Keep the expected section the same so we can compare what the differences are. On the Cash tab of the desk_tickets.html file we want to itemize all the money. Write the starting checking balance (after we reset the DB), the cash changes for each ticket and why the cash changed (describe the payment/purchase and the dollar amount), and the ending checking balance. Keep in mind the ending checking balance must match the ending balance (cash_accounts) in the working DB. Also create output/resolved_tickets.json where it describes each ticket id with its final status, short description of the outcome, what each agent did to resolve the ticket, and any human interactions with payment/purchase approvals. Also create output/resolved_board.html that has a screenshot of each resolved ticket. Make sure to append the runs to output/audit_trail.json. Also update output/harness.md and make sure it encompasses the whole project by describing the tables, MCP tools, the agents, the routes, the dashboard, and the safety rules (a lot of that should already be there so you may not have to do much for this task for that).
```

## Problem 10: Reflection

### Prompt 1

```
For “Problem 10: Reflection”, update output/desk_tickets.html to fill in the Reflection tab. On that tab you need to have: your evaluation of the agents’ performance on each ticket and why you are evaluating them that way, how the actual plan compared to the expected plan that you wrote before the test, if anything could have been simpler by not using a multi-agent approach and how it would have been simpler, come up with 3 new problems that our agent team could solve and that are realistically something that campus customs might face, come up with 3 new problems that campus customs could face in the future but our agent team could not complete given the current tools they have and then explain what additions would need to be made (both on the agents and the tools side). Make sure all the answers are tied directly to this app and its performance etc and the three tickets that we completed just barely. You should read the data off the tickets and cash tabs for evidence. Be specific, don’t write a generic essay.
```
## Problem 11: Submit to GitHub

### Prompt 1

```
For “Problem 11: Submit to GitHub”, create a README.md file at the root of the project that explains how to run the application. It should detail that you should copy the original DB over the existing copy when you need to reset the DB for a new run. It should also explain how to start the MCP server, the FastAPI backend, the react dashboard, and that you need to do the DB reset before you do a full three-ticket processing run.
```
