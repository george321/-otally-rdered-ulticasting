#Giorgos Mitaros AM: 2312
#Email: gmitaros@gmail.com , cs122312@cse.uoi.gr
#
#Sunergasia me Niko Koulina AM: 2277
#
# python totormu.py 127.0.0.1 0 2312
# python totormu.py 127.0.0.1 1 2313
# python totormu.py 127.0.0.1 2 2314
# 
#

import optparse
import socket
import random
import time
import heapq
import copy
import sys
import threading


from twisted.internet.protocol import ReconnectingClientFactory
from twisted.internet.protocol import Protocol, ClientFactory
from twisted.internet import reactor

connections = 0
transports = []


class Message:

	def __init__(self, id, msg, clock, status, ack,
				originalID, originalClock):        
		self.senderID = id 
		self.message = msg
		self.clock = clock
		self.ready = status
		self.ack = ack
		self.creatorID = originalID
		self.creatorClock = originalClock

	def toString(self):
		string = str(self.senderID)+"."+str(self.message)+"."+str(self.clock)+"."+str(self.ack)+"."+str(self.ready)+"."+str(self.creatorID)+"."+str(self.creatorClock)
		return string

def parse_args():
	usage = """usage: %prog [options] [hostname] [thread number] [port]

	 python totormu.py 127.0.0.1 0 2312 """

	parser = optparse.OptionParser(usage)

	_, args = parser.parse_args()

	if len(args) != 3:
		print parser.format_help()
		parser.exit()

	address, threadNo, port = args

	return address, threadNo, port


class Peer(Protocol):

	connected = False
	counter = 0
	flag = 0
	f= None

	#Message acks block
	acks = {}

	#lamport Clock
	clock = 0

	#Queue
	queue = []

	#Locks
	clockLock = threading.Lock()
	socketsLock = threading.Lock()
	queueLock = threading.Lock()

	def __init__(self, factory):
		self.factory = factory

	def connectionMade(self):
		print "Connection Happened"
		global connections
		connections += 1
		global transports
		transports.append(self.transport)
		print "procNo: " + procNo + " connections: " + str(connections)
		if (connections == 2):
			#Ftiaxnw to arxeio gia na grafw ta minimata pou lamvanw
			fileName ="delivered-messages-"+str(procNo) 
			self.f = open(fileName, 'w')
			self.clock = int(procNo)
			print "I begin with clock ", str(self.clock) 
			self.loop()

	def loop(self):
		#Write message
		if (self.flag < 20 ):
			if (int(procNo) == 0):
				send = Message((procNo), str(int(procNo)+1), (self.clock), False, False, int(procNo), int(self.clock))
				self.sendUpdate(send)
			elif (int(procNo)  == 1):
				send = Message((procNo), str(int(procNo)+2), (self.clock), False, False, int(procNo), int(self.clock))
				self.sendUpdate(send)
			elif (int(procNo)  == 2):
				send = Message((procNo), str(int(procNo)+3), (self.clock), False, False, int(procNo), int(self.clock))
				self.sendUpdate(send)

			v = self.deliverMessage()           
			while v: 
				if not v.ack:
					self.counter = self.counter + int(v.message)
					print str(self.flag)+": O ", v.senderID, " leei +", v.message , " my counter was: " , str(self.counter-int(v.message)), " my counter: " , str(self.counter)
					(self.f).write(str(self.flag)+": O "+ str(v.senderID)+ " leei +"+ str(v.message) + " my counter was: " + str(self.counter-int(v.message))+ " my counter: " + str(self.counter)+"\n")
					v = self.deliverMessage()

			reactor.callLater(2, self.loop)
			self.flag+=1
		else:
			v = self.deliverMessage()           
			while v: 
				if not v.ack:
					self.counter = self.counter + int(v.message)
					print str(self.flag)+": O ", v.senderID, " leei +", v.message , " my counter was: " , str(self.counter-int(v.message)), " my counter: " , str(self.counter)
					(self.f).write(str(self.flag)+": O "+ str(v.senderID)+ " leei +"+ str(v.message) + " my counter was: " + str(self.counter-int(v.message))+ " my counter: " + str(self.counter)+"\n")
					v = self.deliverMessage()
			reactor.callLater(2, self.loop)
		

	def deliverMessage(self):
		message = None
		self.queueLock.acquire()

		if len(self.queue) > 0:
			# pairnw to prwto stoixeio apo tin oura(FIFO)
			priority, m = heapq.heappop(self.queue)

			# elegxw an einai ready
			if m.ready:                        
				message = m

			# to ksana vazw pisw ean den einai etoimo
			else:
				heapq.heappush(self.queue, (priority, m))

		self.queueLock.release()
		return message

	def sendUpdate(self, message):

		#Safely change clock
		self.clockLock.acquire()
		self.clock += 1
		self.clockLock.release()
		
		
		#Edit the message.clock before send
		message.clock = self.clock
		message.senderID = procNo

		#Vazw paules gia na min mplekontai ta minimata metaksi tous
		msg = message.toString()
		msg = "-"+msg+"-|/"

		#Stelnw se olous kai ston eauto mou
		self.socketsLock.acquire()
		try:
			#To stelnw ston eauto mou 
			self.totalOrder(message)
			#To stelnw kai stous allous
			global transports
			for transport in transports:
				transport.write(msg)
		except Exception, ex1:
			print "Exception trying to send: ", ex1.args[0]
		self.socketsLock.release()

	def sendAck(self):
		self.ts = time.time()
		try:
			self.transport.write('<Ack> from '+ str(procNo))
		except Exception, e:
			print e.args[0]

	def totalOrder(self, msg):
		# Lamport Clock Update
		self.clockLock.acquire()
		self.clock = max(int(msg.clock), int(self.clock)) + 1
		self.clockLock.release()
		
		id = (msg.creatorID, msg.creatorClock)

		if id in self.acks:
			if msg.ack:
				self.acks[id].append(msg)  
			else:
				# Einai original minima to vazw stin arxi"
				self.acks[id].insert(0, msg)
		else:
			#Auto to mnm erxetai gia prwti fora kai to vazoume stin lista mas"
			self.acks[id] = [msg]

		self.queueLock.acquire()

		if not msg.ack:
			#Den einai ACK opote to vazw stin oura mas (FIFO)
			heapq.heappush(self.queue, ((msg.creatorClock, msg.creatorID), msg))

		# Elava ola ta ACKs kai to markarw san etoimo
		if len(self.acks[id]) == 3:		
			self.acks[id][0].ready = True
			del self.acks[id]

		# Kanw ena antigrafo tou minimatos
		copyMessage = copy.copy(msg)
		self.queueLock.release()

		#Ean den einai ack to minima kai einai oroginal tote to kanw Ack
		if not copyMessage.ack and copyMessage.senderID != procNo:
			copyMessage.ack = True
			self.sendUpdate(copyMessage)

	def dataReceived(self, data):
		msgs= data.split("|")
		start = '-'
		end = '-'
		for minima in msgs:
			#print minima
			if len(minima)>5:
				#Afairw tis paules ('-')
				minima = minima[minima.find(start)+len(start):minima.rfind(end)]
				minima = minima.split(".")
				#Dimiourgw ena antikeimeno tupou Message
				msg = self.createMessage(minima)
				self.totalOrder(msg)
		

	def connectionLost(self, reason):
		print "Disconnected"

	def done(self):
		self.factory.finished(self.acks)

	def createMessage(self, var):
		senderID = var[0]
		text = var[1]
		senderClock = var[2]
		ack = (var[3] == "True")
		ready = (var[4] == "True")
		creatorId = var[5]
		creatorClock = var[6]
		msgObject = Message(int(senderID), text, int(senderClock), ready, ack, int(creatorId), int(creatorClock) )
		
		return msgObject

	def printMsg(self, msg):
		print "senderID", msg.senderID
		print "text", msg.message
		print "senderClock", msg.clock
		print "ack", msg.ack
		print "ready", msg.ready
		print "creatorId", msg.creatorID
		print "creatorClock", msg.creatorClock
		print "--------------"


class PeerFactory(ClientFactory, ReconnectingClientFactory):

	def __init__(self):
		print '@__init__'
		self.acks = 0
		self.records = []

	def finished(self, arg):
		self.acks = arg
		self.report()

	def report(self):
		print 'Received %d acks' % self.acks

	def clientConnectionFailed(self, connector, reason):
		print 'Failed to connect to:', connector.getDestination()
		self.finished(0)

	def clientConnectionLost(self, connector, reason):
		print 'Lost connection.  Reason:', reason
		# Connect to another peer with following host and port
		# Host and port could be read from a list which stores peer information
		connector.host = '127.0.0.1'
		connector.port = 9999
		ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

	def startFactory(self):
		print "@startFactory"

	def stopFactory(self):
		print "@stopFactory"

	def buildProtocol(self, addr):
		print "@buildProtocol"
		protocol = Peer(self)
		return protocol

	

if __name__ == '__main__':
	address, procNo, porta = parse_args()


	if (int(procNo) == 0):
		print "I am process " + procNo 
		print "Addr: "+ address + "\nPort: " + porta
		print "Local ip: " + socket.gethostbyname(socket.gethostname())+"\n"
		port = int(porta)
		server = PeerFactory()
		reactor.listenTCP(port, server)
		print "Starting server @" + address + " port " + str(port)
	elif(int(procNo) == 1):
		#Client things
		print "I am process " + procNo 
		factory = PeerFactory()
		port = int(porta) - 1
		print "Connecting to host " + address + " port " + str(port)
		reactor.connectTCP(address, port, factory)
		#Server things
		server2 = PeerFactory()
		reactor.listenTCP(int(porta), server2)
		print "Starting server @" + address + " port " + str(porta)
	elif(int(procNo) == 2):
		print "I am process " + procNo
		client3 = PeerFactory()
		factory2 = PeerFactory()
		port1 = int(porta) - 1
		port2 = int(porta) - 2
		print "Connecting to host " + address + " port " + str(port1)
		reactor.connectTCP(address, port1, client3)
		print "Connecting to host " + address + " port " + str(port2)
		reactor.connectTCP(address, port2, factory2)

	reactor.run()
