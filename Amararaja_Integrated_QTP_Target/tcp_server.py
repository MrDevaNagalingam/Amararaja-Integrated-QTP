import socket
import config
from dispatcher import dispatch
from qtp_protocol import Connection, REQUEST, STREAM, RESULT


def serve(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(1)
        print("[QTP] Listening on {}:{}...".format(host, server.getsockname()[1]), flush=True)
        while True:
            conn, addr = server.accept()
            print("[QTP] PC connected: {}:{}".format(*addr), flush=True)
            stop = False
            with conn:
                conn.settimeout(config.SOCKET_TIMEOUT)
                connection = Connection(conn)
                try:
                    while True:
                        # Idle operators may stay connected indefinitely. A partially
                        # received frame must complete within SOCKET_TIMEOUT.
                        conn.settimeout(None if not connection.buffer else config.SOCKET_TIMEOUT)
                        if not connection.buffer:
                            data = conn.recv(4096)
                            if not data:
                                raise ConnectionError("PC disconnected")
                            connection.buffer.extend(data)
                        conn.settimeout(config.SOCKET_TIMEOUT)
                        kind, request_id, request = connection.receive()
                        if kind != REQUEST:
                            raise ValueError("Expected request frame")
                        command = request.get("command")
                        print("[HOST] PC -> TARGET: {} (request {})".format(command, request_id), flush=True)
                        result, stop = dispatch(request)
                        connection.send(STREAM, request_id, {"message": "Received command: {}".format(command)})
                        connection.send(RESULT, request_id, result)
                        if stop:
                            break
                except (OSError, ValueError) as exc:
                    print("[QTP] Connection closed: " + str(exc), flush=True)
            if stop:
                return
            print("[QTP] Waiting for host reconnection", flush=True)
