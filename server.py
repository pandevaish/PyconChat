import socket
import threading
import pickle
import os

groups = {}
fileTransferCondition = threading.Condition()

class Group:
	def __init__(self,admin,client):
		self.admin = admin
		self.clients = {}
		self.offlineMessages = {}
		self.allMembers = set()
		self.onlineMembers = set()
		self.joinRequests = set()
		self.waitClients = {}

		self.clients[admin] = client
		self.allMembers.add(admin)
		self.onlineMembers.add(admin)

	def disconnect(self,username):
		self.onlineMembers.remove(username)
		del self.clients[username]
	
	def connect(self,username,client):
		self.onlineMembers.add(username)
		self.clients[username] = client

	def sendMessage(self,message,username):
		for member in self.onlineMembers:
			if member != username:
				self.clients[member].send(bytes(username + ": " + message,"utf-8"))

def pyconChat(client):
	while True:
		msg = client.recv(1024).decode("utf-8")
		if msg == "/viewRequests":
			client.send(b"/viewRequests")
			username = client.recv(1024).decode("utf-8")
			client.send(b"/sendGroupname")
			groupname = client.recv(1024).decode("utf-8")
			if username == groups[groupname].admin:
				client.send(b"/sendingData")
				client.recv(1024)
				client.send(pickle.dumps(groups[groupname].joinRequests))
			else:
				client.send(b"You're not an admin.")
		elif msg == "/approveRequest":
			client.send(b"/approveRequest")
			username = client.recv(1024).decode("utf-8")
			client.send(b"/sendGroupname")
			groupname = client.recv(1024).decode("utf-8")
			if username == groups[groupname].admin:
				client.send(b"/proceed")
				username = client.recv(1024).decode("utf-8")
				if username in groups[groupname].joinRequests:
					groups[groupname].joinRequests.remove(username)
					groups[groupname].allMembers.add(username)
					if username in groups[groupname].waitClients:
						groups[groupname].waitClients[username].send(b"/accepted")
						groups[groupname].connect(username,groups[groupname].waitClients[username])
						del groups[groupname].waitClients[username]
					print("Member Approved:",username,"| Group:",groupname)
					client.send(b"User has been added to the group.")
				else:
					client.send(b"The user has not requested to join.")
			else:
				client.send(b"You're not an admin.")
		elif msg == "/disconnect":
			client.send(b"/disconnect")
			username = client.recv(1024).decode("utf-8")
			client.send(b"/sendGroupname")
			groupname = client.recv(1024).decode("utf-8")
			groups[groupname].disconnect(username)
			print("User Disconnected:",username,"| Group:",groupname)
			break
		elif msg == "/messageSend":
			client.send(b"/messageSend")
			username = client.recv(1024).decode("utf-8")
			client.send(b"/sendGroupname")
			groupname = client.recv(1024).decode("utf-8")
			client.send(b"/sendMessage")
			message = client.recv(1024).decode("utf-8")
			groups[groupname].sendMessage(message,username)
		elif msg == "/waitDisconnect":
			client.send(b"/waitDisconnect")
			username = client.recv(1024).decode("utf-8")
			client.send(b"/sendGroupname")
			groupname = client.recv(1024).decode("utf-8")
			del groups[groupname].waitClients[username]
			print("Waiting Client:",username,"Disconnected")
		elif msg == "/allMembers":
			client.send(b"/allMembers")
			username = client.recv(1024).decode("utf-8")
			client.send(b"/sendGroupname")
			groupname = client.recv(1024).decode("utf-8")
			client.send(pickle.dumps(groups[groupname].allMembers))
		elif msg == "/onlineMembers":
			client.send(b"/onlineMembers")
			username = client.recv(1024).decode("utf-8")
			client.send(b"/sendGroupname")
			groupname = client.recv(1024).decode("utf-8")
			client.send(pickle.dumps(groups[groupname].onlineMembers))
		elif msg == "/changeAdmin":
			client.send(b"/changeAdmin")
			username = client.recv(1024).decode("utf-8")
			client.send(b"/sendGroupname")
			groupname = client.recv(1024).decode("utf-8")
			if username == groups[groupname].admin:
				client.send(b"/proceed")
				username = client.recv(1024).decode("utf-8")
				if username in groups[groupname].allMembers:
					groups[groupname].admin = username
					print("New Admin:",username,"| Group:",groupname)
					client.send(b"Your adminship is now transferred to the specified user.")
				else:
					client.send(b"The user is not a member of this group.")
			else:
				client.send(b"You're not an admin.")
		elif msg == "/whoAdmin":
			client.send(b"/whoAdmin")
			groupname = client.recv(1024).decode("utf-8")
			client.send(bytes("Admin: "+groups[groupname].admin,"utf-8"))
		elif msg == "/kickMember":
			client.send(b"/kickMember")
			username = client.recv(1024).decode("utf-8")
			client.send(b"/sendGroupname")
			groupname = client.recv(1024).decode("utf-8")
			if username == groups[groupname].admin:
				client.send(b"/proceed")
				username = client.recv(1024).decode("utf-8")
				if username in groups[groupname].allMembers:
					groups[groupname].allMembers.remove(username)
					if username in groups[groupname].onlineMembers:
						groups[groupname].clients[username].send(b"/kicked")
						groups[groupname].onlineMembers.remove(username)
						del groups[groupname].clients[username]
					print("User Removed:",username,"| Group:",groupname)
					client.send(b"The specified user is removed from the group.")
				else:
					client.send(b"The user is not a member of this group.")
			else:
				client.send(b"You're not an admin.")
		elif msg == "/fileTransfer":
			client.send(b"/fileTransfer")
			username = client.recv(1024).decode("utf-8")
			client.send(b"/sendGroupname")
			groupname = client.recv(1024).decode("utf-8")
			client.send(b"/sendFilename")
			filename = client.recv(1024).decode("utf-8")
			client.send(b"/sendFile")
			remaining = int.from_bytes(client.recv(4),'big')
			f = open(filename,"wb")
			while remaining:
				data = client.recv(min(remaining,4096))
				remaining -= len(data)
				f.write(data)
			f.close()
			print("File received:",filename,"| User:",username,"| Group:",groupname)
			for member in groups[groupname].onlineMembers:
				if member != username:
					memberClient = groups[groupname].clients[member]
					memberClient.send(b"/receiveFile")
					with fileTransferCondition:
						fileTransferCondition.wait()
					memberClient.send(bytes(filename,"utf-8"))
					with fileTransferCondition:
						fileTransferCondition.wait()
					with open(filename,'rb') as f:
						data = f.read()
						dataLen = len(data)
						memberClient.send(dataLen.to_bytes(4,'big'))
						memberClient.send(data)
			client.send(bytes(filename+" successfully sent to all online group members.","utf-8"))
			print("File sent",filename,"| Group: ",groupname)
			os.remove(filename)
		elif msg == "/sendFilename" or msg == "/sendFile":
			with fileTransferCondition:
				fileTransferCondition.notify()
		else:
			print("UNIDENTIFIED COMMAND:",msg)
def handshake(client):
	username = client.recv(1024).decode("utf-8")
	client.send(b"/sendGroupname")
	groupname = client.recv(1024).decode("utf-8")
	if groupname in groups:
		if username in groups[groupname].allMembers:
			groups[groupname].connect(username,client)
			client.send(b"/ready")
			print("User Connected:",username,"| Group:",groupname)
		else:
			groups[groupname].joinRequests.add(username)
			groups[groupname].waitClients[username] = client
			groups[groupname].sendMessage(username+" has requested to join the group.","PyconChat")
			client.send(b"/wait")
			print("Join Request:",username,"| Group:",groupname)
		threading.Thread(target=pyconChat, args=(client,)).start()
	else:
		groups[groupname] = Group(username,client)
		threading.Thread(target=pyconChat, args=(client,)).start()
		client.send(b"/adminReady")
		print("New Group:",groupname,"| Admin:",username)

if __name__ == "__main__":
	ip = '127.0.0.1'
	port = 8001
	listenSocket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
	listenSocket.bind((ip,port))
	listenSocket.listen(10)
	print("PyconChat Server running")
	while True:
		client,_ = listenSocket.accept()
		threading.Thread(target=handshake, args=(client,)).start()