/* Synthetic UART/module model; never a vehicle measurement. */
#include "Bluetooth.h"
#include "usart.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
UART_HandleTypeDef huart2;
static uint32_t tick,baud=9600;
static int connected=1,present=1;
static const char *response="";
int HAL_UART_Init(UART_HandleTypeDef *h){(void)h;return HAL_OK;}
uint32_t HAL_GetTick(void){return tick++;}
void HAL_Delay(uint32_t ms){tick+=ms;}
void Error_Handler(void){assert(0);}
void MX_USART2_UART_Init(void){huart2.Init.BaudRate=115200;}
int HAL_UART_Transmit(UART_HandleTypeDef *h,uint8_t *p,uint16_t n,uint32_t timeout){
    char cmd[40];(void)timeout;assert(n<sizeof(cmd));memcpy(cmd,p,n);cmd[n]=0;
    assert(!strcmp(cmd,"AT+DISC\r\n")||!strcmp(cmd,"AT+VERSION\r\n")||!strcmp(cmd,"AT+BAUD8\r\n")||!strcmp(cmd,"AT+BAUD\r\n"));
    response="";if(!present||h->Init.BaudRate!=baud)return HAL_OK;
    if(!strcmp(cmd,"AT+DISC\r\n")){connected=0;response="+OK\r\n";}
    else if(!connected&&!strcmp(cmd,"AT+VERSION\r\n"))response="+VERSION=JDY-33-V1.6\r\n";
    else if(!connected&&!strcmp(cmd,"AT+BAUD8\r\n")){baud=115200;response="+OK\r\n";}
    else if(!connected&&!strcmp(cmd,"AT+BAUD\r\n"))response="+BAUD=8\r\n";
    return HAL_OK;
}
int HAL_UART_Receive(UART_HandleTypeDef *h,uint8_t *p,uint16_t n,uint32_t timeout){
    (void)n;tick+=timeout;if(h->Init.BaudRate!=baud||!*response)return 1;*p=(uint8_t)*response++;return HAL_OK;
}
int main(void){
    Bluetooth_Bootstrap();assert(Bluetooth_DetectedBaud()==9600);assert(Bluetooth_ATVerified());
    assert(baud==115200&&huart2.Init.BaudRate==115200);
    present=0;Bluetooth_Bootstrap();assert(!Bluetooth_ATVerified()&&Bluetooth_DetectedBaud()==0);
    assert(huart2.Init.BaudRate==115200);puts("Synthetic JDY-33 setup and stale-verification checks passed.");return 0;
}
