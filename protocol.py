import json
import struct

#SEND MESSAGE
def send_msg(sock, message):
    """ Send a complete JSON message through TCP. """

    json_data = json.dumps(message)
    data = json_data.encode("utf-8")
    message_length = len(data)
    header = struct.pack("!I", message_length)
    sock.sendall( header + data)

#RECEIVE EXACT BYTES
def recv_exact(sock, number_of_bytes):
    """ Receive exactly number_of_bytes from TCP socket."""

    data = b""
    while len(data) < number_of_bytes:
        chunk = sock.recv(
            number_of_bytes - len(data)
        )

        if not chunk:
            raise ConnectionError("Peer disconnected.")
        data += chunk
    return data

#RECEIVE MESSAGE
def recv_msg(sock):
    """ Receive one complete framed JSON message. """

    header = recv_exact(sock,4)
    message_length = struct.unpack("!I",header)[0]
    data = recv_exact(sock,message_length)
    json_data = data.decode("utf-8")
    message = json.loads(json_data)
    return message

#CREATE HELLO MESSAGE
def make_hello(peer_id, name, port, ip):
    """ Create a HELLO message. """

    return {"type": "hello", "peer_id": peer_id, "peer_name": name, "port": port, "ip": ip}


#CREATE HELLO ACK MESSAGE
def make_hello_ack(peer_id, name, port, ip):
    """ Create a HELLO acknowledgement message."""

    return {"type": "hello_ack", "peer_id": peer_id, "peer_name": name, "port": port, "ip": ip}


#CREATE TEXT MESSAGE
def make_text(peer_id, name, message):
    """ Create a text message. """

    return { "type": "text", "sender_id": peer_id,"sender_name": name,"message": message}

#CREATE FILE MESSAGE
def make_file(peer_id, name, filename, filesize):
    """ Create file metadata. """
    
    return { "type": "file", "sender_id": peer_id, "sender_name": name, "filename": filename,"filesize": filesize }