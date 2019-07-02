'''
name:Airclient ,group:303b ,author:黄若鹏2016212901
注：这里IP地址，默认本机。如要多机测试，需要修改ip地址，
连接server端的在12行附近，连接测试程序的在135行附近。
如要修改房间号，在21左右。
'''
import socket
import time
import threading

#连接Server
Sersocket=socket.socket()
SerAddr=('127.0.0.1', 5555)

#SerAddr=('192.168.3.212', 5555)
#SerAddr=('192.168.3.188', 5555)
Sersocket.connect((SerAddr))

class MyGlobal:
    def __init__(self):
        self.r=1 #romm 房间号      
        self.it=0 #init temp,初始温度
        self.t=0 #temp 房间当前温度
        self.tt=0 #target temp,设置房间目标温度
        self.ptc=0 #previous temp tick 上一次修改温度的tick
        self.w=0 #wind,空调风速档位
        self.tc=0 #tick counter,消息发送时的tick计数
        self.ts=2 #tick second,每个tick使用的时长（单位：秒）可以是小数
        self.stop=0 #空调是否关闭
        self.start=0 #是否可以向服务器端发送
        self.count=0
        self.intic=0#初始tic
GL = MyGlobal()

def init(msg):
    msg=msg.strip()
    #print('q'+msg)
    msg_list=msg.split()
    
    GL.it=int((msg_list[0].split('='))[1])
    GL.t=GL.it
    GL.tt=int((msg_list[1].split('='))[1])
    GL.w=int((msg_list[2].split('='))[1])
    GL.tc=int((msg_list[3].split('='))[1])
    GL.ptc=GL.tc
    GL.intic=GL.tc
    GL.ts=float((msg_list[4].split('='))[1])

#监听来自T的消息
def recvT(Tsocket,Sersocket):
    #print('recvT')
    while(GL.stop==0):    
        msg=Tsocket.recv(1024)      
        msg=msg.decode('utf-8').strip()
        
        msg_list=msg.split()

        if msg.strip():
            print('recvTmsg='+msg+' GL.tc='+str(GL.tc))
            if (msg_list[0].split('='))[0]=='w':
                Sersocket.send(('r='+str(GL.r)+' '+msg_list[1]+' w=0\n').encode('utf-8'))

                w_val=int((msg_list[0].split('='))[1])
                if w_val==0:
                    GL.stop=1;#关闭空调
              

            elif (msg_list[0].split('='))[0]=='it':
                init(msg)
                GL.start=1
  
def timer(Sersocket):  

    if GL.stop==1:#空调关闭
        return

    tim=threading.Timer(GL.ts,timer,(Sersocket,))#一个tick检查一下
    tim.start() 
    #print('k')

    if GL.start==1:
        if GL.tc==GL.intic:
            Sersocket.send(('r='+str(GL.r)+' tc='+str(GL.tc)+' t='+str(GL.t)+'\n').encode('utf-8')) 
            #print(('r='+str(GL.r)+' tc='+str(GL.tc)+' t='+str(GL.t)).encode('utf-8'))
        else:          
        
            if GL.t>GL.tt:#当房间温度高于设定温度时
                if GL.w==3:
                    GL.t=GL.t-1
                    Sersocket.send(('r='+str(GL.r)+' tc='+str(GL.tc)+' t='+str(GL.t)+'\n').encode('utf-8'))
                    GL.ptc=GL.tc
                elif GL.w==2:
                    if GL.tc-GL.ptc==2:
                        GL.t=GL.t-1
                        Sersocket.send(('r='+str(GL.r)+' tc='+str(GL.tc)+' t='+str(GL.t)+'\n').encode('utf-8'))
                        GL.ptc=GL.tc
                elif GL.w==1:
                    if GL.tc-GL.ptc==3:
                        GL.t=GL.t-1
                        Sersocket.send(('r='+str(GL.r)+' tc='+str(GL.tc)+' t='+str(GL.t)+'\n').encode('utf-8'))
                        GL.ptc=GL.tc

            elif GL.t==GL.tt:#当房间温度等于设定温度时，每一个tic发送一次
                if GL.stop==1:#空调关闭
                    Sersocket.send(('tc='+str(GL.tc)+' w=0\n').encode('utf-8'))
                else:
                    Sersocket.send(('r='+str(GL.r)+' tc='+str(GL.tc)+' t='+str(GL.t)+'\n').encode('utf-8'))
            
            elif GL.t<GL.tt:#当房间温度低于设定温度时
                if GL.w==3:
                    GL.t=GL.t+1
                    Sersocket.send(('r='+str(GL.r)+' tc='+str(GL.tc)+' t='+str(GL.t)+'\n').encode('utf-8'))
                    GL.ptc=GL.tc
                elif GL.w==2:
                    if GL.tc-GL.ptc==2:
                        GL.t=GL.t+1
                        Sersocket.send(('r='+str(GL.r)+' tc='+str(GL.tc)+' t='+str(GL.t)+'\n').encode('utf-8'))
                        GL.ptc=GL.tc
                elif GL.w==1:
                    if GL.tc-GL.ptc==3:
                        GL.t=GL.t+1
                        Sersocket.send(('r='+str(GL.r)+' tc='+str(GL.tc)+' t='+str(GL.t)+'\n').encode('utf-8'))
                        GL.ptc=GL.tc

        #print(('r='+str(GL.r)+' tc='+str(GL.tc)+' t='+str(GL.t)).encode('utf-8'))    
        GL.tc+=1
            




if __name__ == '__main__':

    #连接T
    Tsocket=socket.socket()
    TAddr = ('127.0.0.1', 9000)
    #TAddr = ('192.168.2.10', 9000)

    Tsocket.connect(TAddr)
    s='k=ETWHC5 r='+str(GL.r)+'\n'
    Tsocket.send(s.encode('utf-8'))
    ack=Tsocket.recv(1024).strip()
   
    timer(Sersocket)

    while True:
        recvT(Tsocket,Sersocket)


    


   
    
    

