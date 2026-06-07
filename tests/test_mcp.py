"""Test MCP server protocol handling."""
from __future__ import annotations
import json
import pytest
from unittest.mock import AsyncMock, patch


class TestMCPProtocol:
    def test_list_tools_response(self):
        from app.mcp.server import MCPServer
        server = MCPServer()

        # Test initialize
        import asyncio
        req = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
        resp = asyncio.run(server.handle_request(req))
        assert resp["result"]["protocolVersion"] == "2024-11-05"
        assert "tools" in resp["result"]["capabilities"]

        # Test list_tools
        req = {"jsonrpc": "2.0", "id": 2, "method": "list_tools"}
        resp = asyncio.run(server.handle_request(req))
        assert "tools" in resp["result"]
        tool_names = [t["name"] for t in resp["result"]["tools"]]
        assert "get_market_data" in tool_names
        assert "calculate_factors" in tool_names
        assert "run_backtest" in tool_names
        assert "generate_signal" in tool_names
        assert "save_memory" in tool_names
        assert "query_memory" in tool_names
        assert "execute_sandbox_order" in tool_names
        assert "generate_daily_report" in tool_names
        assert "get_portfolio" in tool_names
        assert "get_funding_rate" in tool_names

    def test_unknown_method(self):
        from app.mcp.server import MCPServer
        import asyncio
        server = MCPServer()
        req = {"jsonrpc": "2.0", "id": 1, "method": "unknown"}
        resp = asyncio.run(server.handle_request(req))
        assert "error" in resp
        assert resp["error"]["code"] == -32000
