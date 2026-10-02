#include "WheelResponseExperiment.h"
#include "WheelResponseEngine.h"
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "Motor.h"
#include "usart.h"
#include <stdio.h>
#include <string.h>
#include <limits.h>
#include "WheelResponseBuildIdentity.h"
#include "Bluetooth.h"
#define SAMPLE_DEPTH 32
#define ACK_DEPTH 8
#define RX_DEPTH 512
static WRS_Engine engine;
static WRS_Parser parser[2];
static Encoder_t last_counts;
static QueueHandle_t samples,acks;
static StaticQueue_t sample_queue,ack_queue;
static uint8_t sample_storage[SAMPLE_DEPTH*sizeof(WRS_Sample)],ack_storage[ACK_DEPTH*15];
static uint8_t rx_ring[2][RX_DEPTH],rx_byte[2],tx_buffer[1034];
static volatile uint16_t rx_head[2],rx_tail[2],io_faults;
static volatile uint8_t tx_busy,drive_ready,config_pending;
static volatile uint8_t maintenance_pending;
static volatile uint8_t link_owner; /* written only by control task, also read by ISR */
static UART_HandleTypeDef *tx_uart;
static volatile uint32_t bt_rx_bytes,bt_uart_errors,bt_last_error;
static UART_HandleTypeDef *link_uart(unsigned link){return link?&huart2:&huart3;}
static int uart_link(UART_HandleTypeDef *h){return h->Instance==USART3?0:h->Instance==USART2?1:-1;}
static uint32_t sequence,drop_count;
static uint16_t deadline_misses;
static TaskHandle_t control_handle,uart_handle;
static Robot_t robot;
void WRS_EmergencyZero(void){if(drive_ready)Set_PWM(0,0,0,0);}
static void reset_pi(void){
    MotorParam_t *m[4]={&robot.MotorA,&robot.MotorB,&robot.MotorC,&robot.MotorD};unsigned i;
    memset(&robot.MoveSpeed,0,sizeof(robot.MoveSpeed));
    for(i=0;i<4;i++){m[i]->Motor_PWM=0;m[i]->Bias=0;m[i]->Last_bias=0;m[i]->Target=0;}
    Set_PWM(0,0,0,0);engine.reset_pi=0;
}
void WRS_Init(void){
    WRS_EngineInit(&engine);memset(&robot,0,sizeof(robot));
    robot.MotorA.Velocity_KP=robot.MotorB.Velocity_KP=robot.MotorC.Velocity_KP=robot.MotorD.Velocity_KP=VELOCITY_PI_KP;
    robot.MotorA.Velocity_KI=robot.MotorB.Velocity_KI=robot.MotorC.Velocity_KI=robot.MotorD.Velocity_KI=VELOCITY_PI_KI;
    samples=xQueueCreateStatic(SAMPLE_DEPTH,sizeof(WRS_Sample),sample_storage,&sample_queue);
    acks=xQueueCreateStatic(ACK_DEPTH,15,ack_storage,&ack_queue);
    Set_PWM(0,0,0,0);drive_ready=1;
    if(!samples||!acks||WRS_CRC((const uint8_t *)"123456789",9)!=0x29b1)WRS_Fault(&engine,WRS_F_MEMORY);
}
void WRS_RecordEncoder(const Encoder_t *c){last_counts=*c;}
/* ISR only copies bytes; no RTOS API, float formatting, or parsing. */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *h){
    int link=uart_link(h);
    if(link>=0){uint16_t next=(uint16_t)((rx_head[link]+1)%RX_DEPTH);
        if(link==1)bt_rx_bytes++;
        if(next==rx_tail[link]){if(link==link_owner)io_faults|=WRS_F_RX;}
        else {rx_ring[link][rx_head[link]]=rx_byte[link];__DMB();rx_head[link]=next;}
        if(HAL_UART_Receive_IT(h,&rx_byte[link],1)!=HAL_OK&&link==link_owner)io_faults|=WRS_F_UART;
    }
}
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *h){if(h==tx_uart){__DMB();tx_busy=0;}}
void HAL_UART_ErrorCallback(UART_HandleTypeDef *h){
    int link=uart_link(h);
    uint8_t phase=*(volatile uint8_t *)&engine.state;
    if(link>=0){
        if(link==1){bt_uart_errors++;bt_last_error=h->ErrorCode;}
        /* Idle wireless connect/disconnect noise is diagnostic, not a moving session.
         * During ARMED/RUNNING/POST the same UART error still immediately faults. */
        if(link==link_owner&&(link==0||phase==WRS_ARMED||phase==WRS_RUNNING||phase==WRS_ZERO_POST))io_faults|=WRS_F_UART;
        HAL_UART_Receive_IT(h,&rx_byte[link],1);
    }
}
static void command(const WRS_Command *c,uint32_t now,uint8_t source){
    uint8_t ack[15],status;
    if(c->opcode==WRS_BT_SETUP){
        if(source!=0||maintenance_pending||config_pending||(engine.state!=WRS_IDLE&&engine.state!=WRS_COMPLETE&&engine.state!=WRS_FAULT))status=WRS_BAD_STATE;
        else if(c->reserved||c->run_id||c->step||c->pre_ms||c->hold_ms||c->post_ms)status=WRS_BAD_PARAMETER;
        else {maintenance_pending=1;status=WRS_OK;}
    }else if(c->opcode==WRS_BT_UART_BAUD){
        static const uint32_t rates[]={9600,19200,38400,57600,115200,128000};
        if(source!=0||maintenance_pending||(engine.state!=WRS_IDLE&&engine.state!=WRS_COMPLETE&&engine.state!=WRS_FAULT))status=WRS_BAD_STATE;
        else if(c->reserved||c->run_id||c->pre_ms||c->hold_ms||c->post_ms||c->step<4||c->step>9)status=WRS_BAD_PARAMETER;
        else {
            taskENTER_CRITICAL();HAL_UART_AbortReceive(&huart2);huart2.Init.BaudRate=rates[c->step-4];
            status=HAL_UART_Init(&huart2)==HAL_OK?WRS_OK:WRS_BAD_STATE;
            __HAL_UART_CLEAR_OREFLAG(&huart2);rx_head[1]=rx_tail[1]=0;memset(&parser[1],0,sizeof(parser[1]));
            if(HAL_UART_Receive_IT(&huart2,&rx_byte[1],1)!=HAL_OK)status=WRS_BAD_STATE;
            taskEXIT_CRITICAL();
        }
    }else if(c->opcode==WRS_ARM&&maintenance_pending)status=WRS_BAD_STATE;
    else if(c->opcode==WRS_ARM&&source==1&&huart2.Init.BaudRate<115200)status=WRS_BAD_STATE;
    else if(c->opcode==WRS_ARM&&config_pending)status=WRS_BAD_STATE;
    else if(c->opcode==WRS_HELLO&&source!=link_owner&&config_pending)status=WRS_BAD_STATE;
    else if(c->opcode==WRS_GET_CONFIG&&config_pending)status=WRS_BAD_STATE;
    else status=WRS_ApplyFromLink(&engine,c,now,source,&link_owner);
    if(c->opcode==WRS_GET_CONFIG&&status==WRS_OK)config_pending=(uint8_t)(source+1);
    if(c->opcode==WRS_HEARTBEAT)return;
    WRS_Put32(ack,c->sequence);ack[4]=c->opcode;ack[5]=status;ack[6]=engine.state;ack[7]=engine.stage;
    WRS_Put16(ack+8,engine.run_id);WRS_Put16(ack+10,0);WRS_Put16(ack+12,engine.faults);
    ack[14]=source;
    if(xQueueSend(acks,ack,0)!=pdPASS)WRS_Fault(&engine,WRS_F_RX);
}
void WRS_ControlTask(void *arg){
    TickType_t wake=xTaskGetTickCount();uint32_t prev=0;uint8_t first=1;unsigned i;
    MotorParam_t *m[4]={&robot.MotorA,&robot.MotorB,&robot.MotorC,&robot.MotorD};
    control_handle=xTaskGetCurrentTaskHandle();
    Set_PWM(0,0,0,0);Motor_Init();Set_PWM(0,0,0,0);Encoder_Init();
    for(i=0;i<2;i++)if(HAL_UART_Receive_IT(link_uart(i),&rx_byte[i],1)!=HAL_OK)WRS_Fault(&engine,WRS_F_UART);
    for(;;){
        uint32_t now,dt;uint16_t step,errors;unsigned link;int c[4];WRS_Command cmd;WRS_Sample s;
        vTaskDelayUntil(&wake,pdMS_TO_TICKS(10));
        now=HAL_GetTick()*1000u;dt=first?10000u:now-prev;first=0;prev=now;
        if(dt>WRS_DEADLINE_US&&deadline_misses!=65535)deadline_misses++;
        if(dt>=WRS_FATAL_DT_US)WRS_Fault(&engine,WRS_F_SCHEDULING);
        /* Consume at most the bounded ring, then take one encoder measurement. */
        for(link=0;link<2;link++){uint16_t consumed=0;
            while(rx_tail[link]!=rx_head[link]&&consumed++<RX_DEPTH/2){uint8_t b=rx_ring[link][rx_tail[link]];rx_tail[link]=(uint16_t)((rx_tail[link]+1)%RX_DEPTH);
                if(WRS_ParseByte(&parser[link],b,&cmd))command(&cmd,HAL_GetTick(),(uint8_t)link);}}
        taskENTER_CRITICAL();errors=io_faults;io_faults=0;taskEXIT_CRITICAL();
        if(errors)WRS_Fault(&engine,errors);
        if(dt>=WRS_FATAL_DT_US)WRS_Fault(&engine,WRS_F_SCHEDULING);
        GetVelocityFromEncoder(&robot);
        c[0]=last_counts.A;c[1]=last_counts.B;c[2]=last_counts.C;c[3]=last_counts.D;
        for(i=0;i<4;i++)if(c[i]<-32768||c[i]>32767)WRS_Fault(&engine,WRS_F_ENCODER);
        step=WRS_BeginCycle(&engine,HAL_GetTick());
        if(engine.reset_pi)reset_pi();
        if(engine.state==WRS_RUNNING||engine.state==WRS_ZERO_POST){
            MoveSpeed_t move={0,0,0};move.X_Speed=step/1000.0f;ROS_Control(&robot,&move);
        }else {memset(&robot.MoveSpeed,0,sizeof(robot.MoveSpeed));Set_PWM(0,0,0,0);}
        memset(&s,0,sizeof(s));s.sequence=sequence++;s.time_us=now;s.dt_us=dt;s.run_id=engine.run_id;
        s.state=engine.state;s.stage=engine.stage;s.v=robot.MoveSpeed.X_Speed;s.w=robot.MoveSpeed.Z_Speed;
        for(i=0;i<4;i++){s.target[i]=m[i]->Target;s.feedback[i]=m[i]->Velocity;s.pwm[i]=(int16_t)m[i]->Motor_PWM;
            s.encoder[i]=(c[i]<-32768||c[i]>32767)?0:(int16_t)c[i];}
        s.battery_mv=65535;s.exec_us=65535;s.faults=engine.faults;s.drops=drop_count;s.misses=deadline_misses;
        /* Low UART rates are diagnostic-only: 10 Hz stopped telemetry, never a motion trial. */
        if(!maintenance_pending&&!(link_owner==1&&huart2.Init.BaudRate<115200&&(s.sequence%10)!=0))
            if(xQueueSend(samples,&s,0)!=pdPASS){drop_count++;engine.faults|=WRS_F_DROPS;}
        /* Save the last POST sample before completing and resetting PI. */
        WRS_EndCycle(&engine);
        if(engine.reset_pi)reset_pi();
    }
}
static int config_json(char *p,size_t n){
    int len=snprintf(p,n,
        "{\"fw\":\"%s\",\"base\":\"8655eb21f9537f84b5a66effc0fdb085a4993a99\",\"cv\":2,"
        "\"link\":%u,\"btbaud\":%u,\"btdetected\":%u,\"btat\":%u,\"btrx\":%u,\"bterr\":%u,"
        "\"btsetup\":%u,\"btreply\":\"%s\",\"btlasterr\":%u,"
        "\"kp\":[%.0f,%.0f,%.0f,%.0f],\"ki\":[%.0f,%.0f,%.0f,%.0f],\"period_us\":10000,"
        "\"diameter_m\":%.6f,\"ppr\":%.0f,\"quadrature\":%d,\"reduction\":%.0f,\"wheel_spacing_m\":%.6f,\"axle_spacing_m\":%.6f,"
        "\"pwm_limit\":%d,\"inverse_limit_m_s\":%.1f,\"allowed_mm_s\":[50,100,180,400],"
        "\"hb_ms\":500,\"time_resolution_us\":1000,\"exec_invalid\":65535,\"battery_invalid\":65535,"
        "\"deadline_us\":15000,\"fatal_dt_us\":30000,\"queue_depth\":32,\"sample_struct_bytes\":%u,"
        "\"heap_free\":%u,\"control_stack_free_words\":%u,\"uart_stack_free_words\":%u,\"clock_hz\":%u,"
        "\"fault_bits\":{\"heartbeat\":1,\"abort\":2,\"scheduling\":4,\"encoder_range\":8,\"rx\":16,\"uart\":32,\"memory\":64,\"drops\":128},"
        "\"encoder_invalid_on_range_fault\":0,\"early_stop\":%u,\"parser_errors\":%u}",
        WRS_BUILD_ID,(unsigned)link_owner,(unsigned)huart2.Init.BaudRate,(unsigned)Bluetooth_DetectedBaud(),(unsigned)Bluetooth_ATVerified(),
        (unsigned)bt_rx_bytes,(unsigned)bt_uart_errors,
        (unsigned)maintenance_pending,Bluetooth_LastReplyHex(),(unsigned)bt_last_error,
        robot.MotorA.Velocity_KP,robot.MotorB.Velocity_KP,robot.MotorC.Velocity_KP,robot.MotorD.Velocity_KP,
        robot.MotorA.Velocity_KI,robot.MotorB.Velocity_KI,robot.MotorC.Velocity_KI,robot.MotorD.Velocity_KI,
        WHEEL_DIAMETER,ENCODER_PPR,ENCODER_PALUS,MOTOR_REDUCTION_RATIO,WHEEL_SPACING,AXLE_SPACING,
        VELOCITY_PI_PWM_LIMIT,WHEEL_TARGET_LIMIT,(unsigned)sizeof(WRS_Sample),(unsigned)xPortGetFreeHeapSize(),
        (unsigned)uxTaskGetStackHighWaterMark(control_handle),(unsigned)uxTaskGetStackHighWaterMark(uart_handle),
        (unsigned)SystemCoreClock,(unsigned)engine.early_stop,(unsigned)(parser[0].errors+parser[1].errors));
    return len>0&&len<=(int)1024&&len<(int)n?len:-1;
}
void WRS_UartTask(void *arg){
    uint8_t ack[15],type=0;uint32_t started=0,transmit_timeout_ms=200;WRS_Sample s;
    uart_handle=xTaskGetCurrentTaskHandle();
    for(;;){uint16_t len=0;uint8_t channel=link_owner;
        if(tx_busy){
            if(HAL_GetTick()-started>transmit_timeout_ms){HAL_UART_AbortTransmit(tx_uart);tx_busy=0;
                taskENTER_CRITICAL();io_faults|=WRS_F_UART;taskEXIT_CRITICAL();}
            vTaskDelay(1);continue;
        }
        if(type==WRS_CONFIG){config_pending=0;type=0;}
        if(maintenance_pending&&uxQueueMessagesWaiting(acks)==0){
            /* Background task only; control task continues zero-drive sampling at 100 Hz.
             * Diagnostic telemetry is explicitly paused to avoid artificial FIFO overflow. */
            xQueueReset(samples);HAL_UART_AbortReceive(&huart2);Bluetooth_Bootstrap();
            taskENTER_CRITICAL();rx_head[1]=rx_tail[1]=0;memset(&parser[1],0,sizeof(parser[1]));
            if(HAL_UART_Receive_IT(&huart2,&rx_byte[1],1)!=HAL_OK)io_faults|=WRS_F_UART;
            maintenance_pending=0;taskEXIT_CRITICAL();
        }
        if(xQueueReceive(acks,ack,0)==pdPASS){channel=ack[14];type=WRS_ACK;len=WRS_Frame(tx_buffer,type,ack,14);}
        else if(config_pending){int n=config_json((char *)tx_buffer+8,1025);
            if(n<0){config_pending=0;taskENTER_CRITICAL();io_faults|=WRS_F_MEMORY;taskEXIT_CRITICAL();continue;}
            channel=(uint8_t)(config_pending-1);type=WRS_CONFIG;len=WRS_Frame(tx_buffer,type,tx_buffer+8,(uint16_t)n);
        }else if(xQueueReceive(samples,&s,0)==pdPASS){
            type=WRS_TELEMETRY;WRS_EncodeSample(tx_buffer+8,&s);len=WRS_Frame(tx_buffer,type,tx_buffer+8,84);
        }
        if(len){tx_uart=link_uart(channel);transmit_timeout_ms=(uint32_t)len*10000u/tx_uart->Init.BaudRate+200u;tx_busy=1;started=HAL_GetTick();
            if(HAL_UART_Transmit_IT(tx_uart,tx_buffer,len)!=HAL_OK){tx_busy=0;
                taskENTER_CRITICAL();io_faults|=WRS_F_UART;taskEXIT_CRITICAL();}
        }else vTaskDelay(1);
    }
}
