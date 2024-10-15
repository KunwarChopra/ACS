import socket

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(('localhost', 65432)) #port local
server_socket.listen(1)  #imcoming call

print("Server listening for a response...")

while True:
    conn, addr = server_socket.accept()
    with conn:
        print(f"Connected by {addr}")
        data = conn.recv(1024)
        if data:
            print(f"Received response: {data.decode()}")  
            if data.decode() == 'Confirm':
                print("User confirmed the appointment.")
            elif data.decode() == 'Cancel':
                print("User canceled the appointment.")
        conn.close()
