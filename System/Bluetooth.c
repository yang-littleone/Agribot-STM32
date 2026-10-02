/* JDY-33 UART bootstrap. Called only before RTOS starts, with zero motor drive.
 * Does not reset defaults, rename the module, change PIN, or issue motion commands.
 * Manufacturer manual: FCC ID 2AXM8-JDY-33, AT commands require CRLF.
 */
#include "Bluetooth.h"
#include "usart.h"
#include <string.h>
static uint32_t detected_baud;
static uint8_t verified;
static char reply_hex[65];
static void set_baud(uint32_t baud){
    huart2.Init.BaudRate=baud;
    if(HAL_UART_Init(&huart2)!=HAL_OK)Error_Handler();
    __HAL_UART_CLEAR_OREFLAG(&huart2);
}
static void exchange(const char *cmd,char *reply,unsigned capacity){
    uint32_t started;unsigned used=0;uint8_t byte;
    __HAL_UART_CLEAR_OREFLAG(&huart2);
    if(HAL_UART_Transmit(&huart2,(uint8_t *)cmd,(uint16_t)strlen(cmd),100)!=HAL_OK){reply[0]=0;return;}
    started=HAL_GetTick();
    while((uint32_t)(HAL_GetTick()-started)<250u){
        if(HAL_UART_Receive(&huart2,&byte,1,5)==HAL_OK&&used+1<capacity)reply[used++]=(char)byte;
    }
    reply[used]=0;
    {static const char hex[]="0123456789ABCDEF";unsigned i,n=used<32?used:32;
        for(i=0;i<n;i++){reply_hex[2*i]=hex[(uint8_t)reply[i]>>4];reply_hex[2*i+1]=hex[(uint8_t)reply[i]&15];}reply_hex[2*n]=0;}
}
void Bluetooth_Bootstrap(void){
    static const uint32_t rates[]={115200,9600,19200,38400,57600,128000,4800,2400};
    char reply[128];unsigned i;uint32_t found=0;
    verified=0;detected_baud=0;reply_hex[0]=0;
    MX_USART2_UART_Init();HAL_Delay(300);
    for(i=0;i<sizeof(rates)/sizeof(rates[0]);i++){
        set_baud(rates[i]);exchange("AT+DISC\r\n",reply,sizeof(reply));HAL_Delay(100);
        exchange("AT+VERSION\r\n",reply,sizeof(reply));
        if(strstr(reply,"JDY-33")){found=rates[i];break;}
    }
    detected_baud=found;
    if(found){
        if(found!=115200){
            exchange("AT+BAUD8\r\n",reply,sizeof(reply));
            HAL_Delay(100);set_baud(115200);
        }
        exchange("AT+BAUD\r\n",reply,sizeof(reply));
        verified=strstr(reply,"+BAUD=8")!=0;
    }else set_baud(115200); /* Connected module may not answer AT; require SPP handshake and raw-data validation. */
}
uint32_t Bluetooth_DetectedBaud(void){return detected_baud;}
uint8_t Bluetooth_ATVerified(void){return verified;}
const char *Bluetooth_LastReplyHex(void){return reply_hex;}
