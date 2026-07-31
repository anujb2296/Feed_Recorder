"""
api/whep.py — WHEP WebRTC proxy endpoint to bypass CORS.
"""
from fastapi import APIRouter, Request, Response
import aiohttp

router = APIRouter(prefix="/whep", tags=["whep"])


@router.api_route("", methods=["POST", "OPTIONS"])
@router.api_route("/", methods=["POST", "OPTIONS"])
async def whep_proxy(request: Request):
    """Proxy WHEP WebRTC SDP requests directly to go2rtc to prevent CORS issues."""
    if request.method == "OPTIONS":
        return Response(status_code=200)

    dst = request.query_params.get("dst", "")
    body = await request.body()

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"http://127.0.0.1:1984/api/whep?dst={dst}",
                data=body,
                headers={"Content-Type": "application/sdp"}
            ) as resp:
                resp_body = await resp.text()
                return Response(
                    content=resp_body,
                    status_code=resp.status,
                    media_type="application/sdp"
                )
        except Exception as e:
            return Response(content=str(e), status_code=500)
