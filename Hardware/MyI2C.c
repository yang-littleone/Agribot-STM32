#include "delay.h"
#include "main.h"
#define I2C_SCL IMU_CLK_Pin		   // I2C的SCL引脚
#define I2C_SDA IMU_SDA_Pin		   // I2C的SDA引脚
#define I2C_PORT IMU_CLK_GPIO_Port // I2C的控制端口

/**
 * @brief  写SCL
 * @param  BitValue，范围：0~1
 * @retval 无
 */
void MyI2C_W_SCL(uint8_t BitValue)
{
	HAL_GPIO_WritePin(I2C_PORT, I2C_SCL, BitValue);
	delay_us(3);
}

/**
 * @brief  写SDA
 * @param  BitValue，范围：0~1
 * @retval 无
 */
void MyI2C_W_SDA(uint8_t BitValue)
{
	HAL_GPIO_WritePin(I2C_PORT, I2C_SDA, BitValue);
	delay_us(3);
}

/**
 * @brief  读SDA
 * @param  无
 * @retval BitValue，范围：0~1
 */
uint8_t MyI2C_R_SDA(void)
{
	uint8_t BitValue;
	BitValue = HAL_GPIO_ReadPin(I2C_PORT, I2C_SDA);
	delay_us(3);

	return BitValue;
}

/**
 * @brief  初始化I2C
 * @param  无
 * @retval 无
 */
void MyI2C_Init(void)
{
	// /*开启时钟*/
	// RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOB, ENABLE); // 开启GPIOA的时钟

	// RCC_APB2PeriphClockCmd(RCC_APB2Periph_AFIO, ENABLE);
	// GPIO_PinRemapConfig(GPIO_Remap_SWJ_JTAGDisable, ENABLE); // 关闭JTAG功能(PB3/4)，只使用SWD(PA13/14)调试

	// /*GPIO初始化*/
	// GPIO_InitTypeDef GPIO_InitStruct;
	// GPIO_InitStruct.GPIO_Mode = GPIO_Mode_Out_OD; // 开漏输出模式
	// GPIO_InitStruct.GPIO_Pin = I2C_SCL | I2C_SDA;
	// GPIO_InitStruct.GPIO_Speed = GPIO_Speed_50MHz;
	// GPIO_Init(I2C_PORT, &GPIO_InitStruct); // 将PA_1 and PA_0设置为50MHZ的推挽输出模式

	// /*设置默认电平*/
	// GPIO_SetBits(I2C_PORT, I2C_SCL | I2C_SDA); // 设置I2C_SCL和I2C_SDA引脚初始化后默认为高电平（释放总线状态）
}

/**
 * @brief  I2C开始单元
 * @param  无
 * @retval 无
 */
void MyI2C_Start(void)
{
	MyI2C_W_SDA(1);
	MyI2C_W_SCL(1);
	MyI2C_W_SDA(0);
	MyI2C_W_SCL(0);
}

/**
 * @brief  I2C停止单元
 * @param  无
 * @retval 无
 */
void MyI2C_Stop(void)
{
	MyI2C_W_SDA(0);
	MyI2C_W_SCL(1);
	MyI2C_W_SDA(1);
}

/**
 * @brief  I2C向从机发送一个字节
 * @param  Byte：范围:0x00~0xFF
 * @retval 无
 */
void MyI2C_SendByte(uint8_t Byte)
{
	uint8_t i;

	MyI2C_W_SCL(0);			// 确保SCL低电平
	for (i = 0; i < 8; i++) // 遍历8位
	{
		MyI2C_W_SDA(Byte & (0x80 >> i));
		MyI2C_W_SCL(1); // 读数据
		MyI2C_W_SCL(0); // 低电平
	}
}

/**
 * @brief  I2C接收从机发来的一个字节
 * @param  无
 * @retval Byte：范围：0x00~0xFF
 */
uint8_t MyI2C_ReceiveByte(void)
{
	uint8_t Byte = 0x00;
	uint8_t i;

	MyI2C_W_SCL(0);
	MyI2C_W_SDA(1);
	for (i = 0; i < 8; i++)
	{
		MyI2C_W_SCL(1);
		if (MyI2C_R_SDA() == 1)
		{
			Byte |= (0x80 >> i);
		}
		MyI2C_W_SCL(0);
	}

	return Byte;
}

/**
 * @brief  I2C向从机发送应答位
 * @param  AckBit，应答位，1：无应答 0：应答
 * @retval 无
 */
void MyI2C_SendAck(uint8_t AckBit)
{
	MyI2C_W_SCL(0);
	MyI2C_W_SDA(AckBit);
	MyI2C_W_SCL(1);
	MyI2C_W_SCL(0);
}

/**
 * @brief  I2C接收从机应答
 * @param  无
 * @retval AckBit，应答位，1：无应答 0：应答
 */
uint8_t MyI2C_ReceiveAck(void)
{
	uint8_t AckBit;

	MyI2C_W_SCL(0);
	MyI2C_W_SDA(1);
	MyI2C_W_SCL(1);
	AckBit = MyI2C_R_SDA();
	MyI2C_W_SCL(0);

	return AckBit;
}
