# TCP QTP framing, version 1

This is the initial protocol defined for this project; no separate wire-format specification was supplied. All integers are unsigned, big endian. TCP is a stream: receivers retain buffered bytes, wait for complete frames, and preserve subsequent frames.

| Header field | Bytes | Value |
| --- | --- | --- |
| Magic | 4 | ASCII AQTP |
| Version | 1 | 1 |
| Request ID | 4 | 1..4294967295 |
| Payload length | 4 | 5..65536, includes TLV header |

Each frame has one TLV: type (1 byte), value length (4 bytes), UTF-8 JSON object (value length bytes). Types: 1=request, 2=stream output, 3=final result. Header payload length must equal 5 + value length.

Request example: `{"command":"ECHO","params":{"text":"hello"}}`.
Stream example: `{"message":"Received command: ECHO"}`.
Result example: `{"status":"PASS","message":"hello"}`.

Responses echo the request ID. One request is outstanding at a time. Results support PASS, FAIL, ERROR, NOT_IMPLEMENTED. STOP_QTP receives a final PASS acknowledgment before the server closes its connection and listener. Invalid headers/TLV/JSON close the client connection; invalid command fields return ERROR; unknown commands return NOT_IMPLEMENTED. Host closes the connection on timeout or protocol errors, avoiding reuse after partial responses. Target permits idle operators and applies a 60-second socket timeout once frame bytes arrive. Host connect timeout is 5 seconds, response timeout is 10 seconds.
