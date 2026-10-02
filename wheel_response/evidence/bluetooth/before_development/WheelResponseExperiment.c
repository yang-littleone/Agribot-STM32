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
#define SAMPLE_DEPTH 32
#define ACK_DEPTH 8
#define RX_DEPTH 512
static WRS_Engine engine;
static WRS_Parser parser;
static Encoder_t last_counts;
static QueueHandle_t samples,acks;
static StaticQueue_t sample_queue,ack_queue;
static uint8_t sample_storage[SAMPLE_DEPTH*sizeof(WRS_Sample)],ack_storage[ACK_DEPTH*14];
static uint8_t rx_ring[RX_DEPTH],rx_byte,tx_buffer[1034];
static volatile uint16_t rx_head,rx_tail,io_faults;
static volatile uint8_t tx_busy,drive_ready,config_pending;
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
    acks=xQueueCreateStatic(ACK_DEPTH,14,ack_storage,&ack_queue);
    Set_PWM(0,0,0,0);drive_ready=1;
    if(!samples||!acks||WRS_CRC((const uint8_t *)"123456789",9)!=0x29b1)WRS_Fault(&engine,WRS_F_MEMORY);
}
void WRS_RecordEncoder(const Encoder_t *c){last_counts=*c;}
/* ISR only copies bytes; no RTOS API, float formatting, or parsing. */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *h){
    if(h->Instance==USART3){uint16_t next=(uint16_t)((rx_head+1)%RX_DEPTH);
        if(next==rx_tail)io_faults|=WRS_F_RX;
        else {rx_ring[rx_head]=rx_byte;__DMB();rx_head=next;}
        if(HAL_UART_Receive_IT(h,&rx_byte,1)!=HAL_OK)io_faults|=WRS_F_UART;
    }
}
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *h){if(h->Instance==USART3){__DMB();tx_busy=0;}}
void HAL_UART_ErrorCallback(UART_HandleTypeDef *h){
    if(h->Instance==USART3){io_faults|=WRS_F_UART;HAL_UART_Receive_IT(h,&rx_byte,1);}
}
static void command(const WRS_Command *c,uint32_t now){
    uint8_t ack[14],status;
    if(c->opcode==WRS_ARM&&config_pending)status=WRS_BAD_STATE;
    else status=WRS_Apply(&engine,c,now);
    if(c->opcode==WRS_GET_CONFIG&&status==WRS_OK)config_pending=1;
    if(c->opcode==WRS_HEARTBEAT)return;
    WRS_Put32(ack,c->sequence);ack[4]=c->opcode;ack[5]=status;ack[6]=engine.state;ack[7]=engine.stage;
    WRS_Put16(ack+8,engine.run_id);WRS_Put16(ack+10,0);WRS_Put16(ack+12,engine.faults);
    if(xQueueSend(acks,ack,0)!=pdPASS)WRS_Fault(&engine,WRS_F_RX);
}
void WRS_ControlTask(void *arg){
    TickType_t wake=xTaskGetTickCount();uint32_t prev=0;uint8_t first=1;unsigned i;
    MotorParam_t *m[4]={&robot.MotorA,&robot.MotorB,&robot.MotorC,&robot.MotorD};
    control_handle=xTaskGetCurrentTaskHandle();
    Set_PWM(0,0,0,0);Motor_Init();Set_PWM(0,0,0,0);Encoder_Init();
    if(HAL_UART_Receive_IT(&huart3,&rx_byte,1)!=HAL_OK)WRS_Fault(&engine,WRS_F_UART);
    for(;;){
        uint32_t now,dt;uint16_t step,errors,consumed=0;int c[4];WRS_Command cmd;WRS_Sample s;
        vTaskDelayUntil(&wake,pdMS_TO_TICKS(10));
        now=HAL_GetTick()*1000u;dt=first?10000u:now-prev;first=0;prev=now;
        if(dt>WRS_DEADLINE_US&&deadline_misses!=65535)deadline_misses++;
        if(dt>=WRS_FATAL_DT_US)WRS_Fault(&engine,WRS_F_SCHEDULING);
        /* Consume at most the bounded ring, then take one encoder measurement. */
        while(rx_tail!=rx_head&&consumed++<RX_DEPTH){uint8_t b=rx_ring[rx_tail];rx_tail=(uint16_t)((rx_tail+1)%RX_DEPTH);
            if(WRS_ParseByte(&parser,b,&cmd))command(&cmd,HAL_GetTick());}
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
        if(xQueueSend(samples,&s,0)!=pdPASS){drop_count++;engine.faults|=WRS_F_DROPS;}
        /* Save the last POST sample before completing and resetting PI. */
        WRS_EndCycle(&engine);
        if(engine.reset_pi)reset_pi();
    }
}
static int config_json(char *p,size_t n){
    int len=snprintf(p,n,
        "{\"fw\":\"%s\",\"base\":\"8655eb21f9537f84b5a66effc0fdb085a4993a99\",\"cv\":1,"
        "\"kp\":[%.0f,%.0f,%.0f,%.0f],\"ki\":[%.0f,%.0f,%.0f,%.0f],\"period_us\":10000,"
        "\"diameter_m\":%.6f,\"ppr\":%.0f,\"quadrature\":%d,\"reduction\":%.0f,\"wheel_spacing_m\":%.6f,\"axle_spacing_m\":%.6f,"
        "\"pwm_limit\":%d,\"inverse_limit_m_s\":%.1f,\"allowed_mm_s\":[50,100,180,400],"
        "\"hb_ms\":500,\"time_resolution_us\":1000,\"exec_invalid\":65535,\"battery_invalid\":65535,"
        "\"deadline_us\":15000,\"fatal_dt_us\":30000,\"queue_depth\":32,\"sample_struct_bytes\":%u,"
        "\"heap_free\":%u,\"control_stack_free_words\":%u,\"uart_stack_free_words\":%u,\"clock_hz\":%u,"
        "\"fault_bits\":{\"heartbeat\":1,\"abort\":2,\"scheduling\":4,\"encoder_range\":8,\"rx\":16,\"uart\":32,\"memory\":64,\"drops\":128},"
        "\"encoder_invalid_on_range_fault\":0,\"early_stop\":%u,\"parser_errors\":%u}",
        WRS_BUILD_ID,robot.MotorA.Velocity_KP,robot.MotorB.Velocity_KP,robot.MotorC.Velocity_KP,robot.MotorD.Velocity_KP,
        robot.MotorA.Velocity_KI,robot.MotorB.Velocity_KI,robot.MotorC.Velocity_KI,robot.MotorD.Velocity_KI,
        WHEEL_DIAMETER,ENCODER_PPR,ENCODER_PALUS,MOTOR_REDUCTION_RATIO,WHEEL_SPACING,AXLE_SPACING,
        VELOCITY_PI_PWM_LIMIT,WHEEL_TARGET_LIMIT,(unsigned)sizeof(WRS_Sample),(unsigned)xPortGetFreeHeapSize(),
        (unsigned)uxTaskGetStackHighWaterMark(control_handle),(unsigned)uxTaskGetStackHighWaterMark(uart_handle),
        (unsigned)SystemCoreClock,(unsigned)engine.early_stop,(unsigned)parser.errors);
    return len>0&&len<=(int)1024&&len<(int)n?len:-1;
}
void WRS_UartTask(void *arg){
    uint8_t ack[14],type=0;uint32_t started=0;WRS_Sample s;
    uart_handle=xTaskGetCurrentTaskHandle();
    for(;;){uint16_t len=0;
        if(tx_busy){
            if(HAL_GetTick()-started>200){HAL_UART_AbortTransmit(&huart3);tx_busy=0;
                taskENTER_CRITICAL();io_faults|=WRS_F_UART;taskEXIT_CRITICAL();}
            vTaskDelay(1);continue;
        }
        if(type==WRS_CONFIG){config_pending=0;type=0;}
        if(xQueueReceive(acks,ack,0)==pdPASS){type=WRS_ACK;len=WRS_Frame(tx_buffer,type,ack,14);}
        else if(config_pending){int n=config_json((char *)tx_buffer+8,1025);
            if(n<0){config_pending=0;taskENTER_CRITICAL();io_faults|=WRS_F_MEMORY;taskEXIT_CRITICAL();continue;}
            type=WRS_CONFIG;len=WRS_Frame(tx_buffer,type,tx_buffer+8,(uint16_t)n);
        }else if(xQueueReceive(samples,&s,0)==pdPASS){
            type=WRS_TELEMETRY;WRS_EncodeSample(tx_buffer+8,&s);len=WRS_Frame(tx_buffer,type,tx_buffer+8,84);
        }
        if(len){tx_busy=1;started=HAL_GetTick();
            if(HAL_UART_Transmit_IT(&huart3,tx_buffer,len)!=HAL_OK){tx_busy=0;
                taskENTER_CRITICAL();io_faults|=WRS_F_UART;taskEXIT_CRITICAL();}
        }else vTaskDelay(1);
    }
}
