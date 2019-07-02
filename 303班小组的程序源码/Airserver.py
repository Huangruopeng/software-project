'''
name:Airserver ,group:303b ,author:黄若鹏2016212901
注：这里IP地址，默认本机。如要多机测试，需要修改ip地址，
连接测试程序的在116行附近。
可以通过第二版测试程序
'''
import string
import time
import threading
import socket

#监听
address='0.0.0.0'#监听哪些网络  127.0.0.1是监听本机 0.0.0.0是监听整个网络
port=5555
sock=socket.socket()
sock.bind((address,port))
sock.listen(4) #最大连接数


class MyGlobal:
    def __init__(self):
        self.b=[0]*5#bill 记录每个房间的账单
        self.ptc=[0]*5 #previous tick记录每个房间到达设定温度时的时刻
        self.ctc=[0]*5 #close tick 关闭空调的时刻
        self.tt=[0]*5 #target temp 记录每个房间的设定温度
        self.pt=[0]*5 #previous temp记录房间之前的温度
        self.it=[0]*5 #init temp,初始温度 户外温度
        self.first=[1]*5 #第一次达到设定温度
        self.tcpcount=0 #tcp连接数量
        self.fticflag=[1]*5 #第一收到client消息
        
GL = MyGlobal()

def listenT(Tsocket):
   # print('listenT')
    while True:
        #print('wait recv')
        msg=Tsocket.recv(1024)
        msg=msg.decode('utf-8').strip()
       
        
        msg_list=msg.split()

        if  msg.strip():           
            if msg_list[0].split('=')[0]=='b':
                rString=msg_list[0].split('=')[1]
                tcString=msg_list[1].split('=')[1]
                r=int(rString)

                if GL.first[r]==0: #到达了目标温度
                    GL.b[r]=abs((GL.it[r]-GL.tt[r]))*(GL.ctc[r]-GL.ptc[r]+1)
                
                else:
                    GL.b[r]=abs((GL.it[r]-GL.tt[r]))

                print(('bill:r='+rString+' tc='+tcString+' b='+str(GL.b[r])+' GL.ctc[r]='+str(GL.ctc[r])+' GL.ptc[r]='+str(GL.ptc[r])+' it='+str(GL.it[r])+ ' tt='+str(GL.tt[r])).encode('utf-8'))
                Tsocket.send(('r='+rString+' tc='+tcString+' b='+str(GL.b[r])+'\n').encode('utf-8'))
       

def tcplink(sock,addr,Tsocket):
    while True:  
        data=sock.recv(1024)
        data=data.decode('utf-8').strip()
       
        if data.strip():
            if data.split()[0].split('=')[0]=='r':   
                Tsocket.send((data+'\n').encode('utf-8'))#转发消息
                
                data_list=data.split(" ")
                if data_list[2].split('=')[0]=='t':
                    r=int((data_list[0].split('='))[1])#房间号
                    tc=int((data_list[1].split('='))[1])#tick
                    #if GL.fticflag==1:
                        #GL.starttic=tc
                    
                    t=int((data_list[2].split('='))[1])#temp
                
                    if GL.fticflag[r]==1:#第一次发过来的信息初始化一下
                        GL.pt[r]=t
                        GL.it[r]=t
                        GL.fticflag[r]=0
                        print(str(t))
                    
                    else:
                        if GL.pt[r]==t: #发过来的温度和之前的温度相同，说明达到设定温度
                            if GL.first[r]==1:#是第一次发生温度相等
                                GL.tt[r]=t
                                GL.ptc[r]=tc-1 #第一次达到设定温度的时刻
                                #GL.b[r]=abs((GL.it[r]-GL.tt[r]))
                                GL.first[r]=0
                            #elif GL.first[r]==0:#维持温度状态
                                #GL.b[r]=GL.b[r]+abs((GL.it[r]-GL.tt[r]))
                        
                        else:
                            GL.pt[r]=t
                           # GL.b[r]=abs((GL.it[r]-t))
                           
                    
                
                elif data_list[2].split('=')[0]=='w':
                    r=int((data_list[0].split('='))[1])#房间号
                    tc=int((data_list[1].split('='))[1])#tick
                    GL.ctc[r]=tc

                  
    

    sock.close()
  

if __name__ == '__main__':
   

    #连接T
    Tsocket=socket.socket()
    TAddr = ('127.0.0.1', 9000)
    #TAddr = ('192.168.2.10', 9000)
    Tsocket.connect(TAddr)
    s='k=ETWHC5 r=s\n'
    Tsocket.send(s.encode('utf-8'))
    ack=Tsocket.recv(1024).strip()
    
    Tt=threading.Thread(target=listenT,args=(Tsocket,))  #t为新创建的线程
    Tt.start()

    while True:
        clientsock,clientaddress=sock.accept()
        #print('connect from:',clientaddress)
        #传输数据都利用clientsock，和s无关
        t=threading.Thread(target=tcplink,args=(clientsock,clientaddress,Tsocket))  #t为新创建的线程
        t.start()
        GL.tcpcount+=1
        #print(GL.tcpcount)
        if GL.tcpcount==4:
            time.sleep(3)#等待所有client都和测试程序都建立连接
            Tsocket.send('i=1\n'.encode('utf-8'))
       
        
           










    

  