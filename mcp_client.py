import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient  
async def main():
    client = MultiServerMCPClient(
        {
            "project-intel": {
                "transport": "stdio",
                "command": "uv",
                "args": [
                    "run",
                    "python",
                    "main.py",
                    "--root",
                    "D:\\year_2026\\GovBD-BackEnd-Python\\AIService",
                ],
            }
        }
    )

    tools = await client.get_tools()
    print(tools)
  

if __name__ == "__main__":
    asyncio.run(main())