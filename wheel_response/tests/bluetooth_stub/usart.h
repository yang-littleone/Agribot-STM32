#ifndef BT_HOST_UART_STUB
#define BT_HOST_UART_STUB
#include <stdint.h>
typedef struct {struct {uint32_t BaudRate;} Init;} UART_HandleTypeDef;
extern UART_HandleTypeDef huart2;
#define HAL_OK 0
#define __HAL_UART_CLEAR_OREFLAG(h) ((void)(h))
int HAL_UART_Init(UART_HandleTypeDef *h);
int HAL_UART_Transmit(UART_HandleTypeDef *h,uint8_t *p,uint16_t n,uint32_t timeout);
int HAL_UART_Receive(UART_HandleTypeDef *h,uint8_t *p,uint16_t n,uint32_t timeout);
uint32_t HAL_GetTick(void);
void HAL_Delay(uint32_t ms);
void Error_Handler(void);
void MX_USART2_UART_Init(void);
#endif
