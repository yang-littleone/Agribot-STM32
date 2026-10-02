"""WRS1 wire format. All integer and float fields are little endian."""
import collections, struct
MAGIC=b'WRS1'
HEADER=struct.Struct('<4sBBH')
TELEMETRY=struct.Struct('<IIIHBBff4f4f4h4hHHIHH')
COMMAND=struct.Struct('<IBBHHHHH')
ACK=struct.Struct('<IBBBBHHH')
assert (TELEMETRY.size,COMMAND.size,ACK.size)==(84,16,14)
OP={'HELLO':1,'ARM':2,'START':3,'STOP':4,'ABORT':5,'HEARTBEAT':6,'DISARM':7,'GET_CONFIG':8,'CLEAR_FAULT':9,'BT_UART_BAUD':10,'BT_SETUP':11}
FIELDS=['sequence','mcu_time_us','cycle_dt_us','run_id','state','stage','cmd_v_m_s','cmd_w_rad_s']
FIELDS += [f'{kind}_{w}_{unit}' for kind,unit in [('target','m_s'),('feedback','m_s'),('pwm','control'),('encoder','counts')] for w in 'ABCD']
FIELDS += ['battery_mv','fault_flags','queue_drop_count','deadline_miss_count','control_exec_us']
CSV_FIELDS=FIELDS+['segment','mcu_time_unwrapped_us','pc_receive_monotonic_ns','sequence_delta','clock_event']
def crc16(data):
    crc=0xffff
    for b in data:
        crc ^= b<<8
        for _ in range(8): crc=((crc<<1)^0x1021 if crc&0x8000 else crc<<1)&0xffff
    return crc
def frame(kind,payload):
    data=HEADER.pack(MAGIC,1,kind,len(payload))+payload
    return data+struct.pack('<H',crc16(data))
def command(seq,opcode,run_id=0,step=0,pre=0,hold=0,post=0):
    return frame(16,COMMAND.pack(seq,OP[opcode],0,run_id,step,pre,hold,post))
class Decoder:
    def __init__(self): self.buffer=bytearray(); self.stats=collections.Counter()
    def noise(self,n):
        self.stats['noise_bytes']+=n
        self.stats['noise_between_frames' if self.stats['frames'] else 'noise_before_first_frame']+=n
    def feed(self,data):
        self.buffer.extend(data); out=[]
        while True:
            pos=self.buffer.find(MAGIC)
            if pos<0:
                trim=max(0,len(self.buffer)-3); self.noise(trim)
                del self.buffer[:trim]; break
            if pos: self.noise(pos); del self.buffer[:pos]
            if len(self.buffer)<8: break
            _,version,kind,size=HEADER.unpack_from(self.buffer)
            if version!=1 or kind not in (1,16,17,18) or (kind!=18 and size!={1:84,16:16,17:14}[kind]) or (kind==18 and size>1024):
                self.stats['bad_header']+=1; del self.buffer[0]; continue
            total=size+10
            if len(self.buffer)<total: break
            packet=bytes(self.buffer[:total])
            if crc16(packet[:-2])!=struct.unpack_from('<H',packet,total-2)[0]:
                self.stats['bad_crc']+=1; del self.buffer[0]; continue
            del self.buffer[:total]; self.stats['frames']+=1
            out.append((kind,packet[8:-2]))
        return out
class ClockTracker:
    """Unwrap normal counters; counter rollback starts a new reboot segment.

    A normal wrap is accepted only near the uint32 boundary. An ambiguous long
    interruption starts a separate segment; no continuity claim crosses it.
    """
    def __init__(self): self.previous=None; self.segment=0; self.expanded=0
    def update(self,seq,t):
        event='normal';delta=0
        if self.previous is None: self.expanded=t;event='first'
        else:
            oldseq,oldt=self.previous; delta=(seq-oldseq)&0xffffffff;dt=(t-oldt)&0xffffffff
            seqwrap=oldseq>0xffff0000 and seq<0x10000
            timewrap=oldt>0xf0000000 and t<0x10000000
            reset=(seq<oldseq and not seqwrap) or (t<oldt and not timewrap) or delta>=0x80000000 or dt>=0x80000000
            if reset: self.segment+=1;self.expanded=t;event='restart_or_ambiguous_gap';delta=0
            elif delta==0: event='duplicate';self.expanded+=dt
            else:
                self.expanded+=dt
                if timewrap: event='time_wrap'
                elif seqwrap: event='sequence_wrap'
        self.previous=seq,t
        return {'segment':self.segment,'mcu_time_unwrapped_us':self.expanded,'sequence_delta':delta,'clock_event':event}
def decode_sample(payload): return dict(zip(FIELDS,TELEMETRY.unpack(payload)))
