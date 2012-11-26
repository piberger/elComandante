/*
 * See uip_TcpAppHub.c for Explanations
 * 
 * Author: Simon Kueppers
 * Email: simon.kueppers@web.de
 * Homepage: http://klinkerstein.m-faq.de
 * 
 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program.  If not, see <http://www.gnu.org/licenses/>.
 
 Copyright 2008 Simon Kueppers
 * */

#include "uip_UdpAppHub.h"
#include "uip.h"

void uip_UdpAppHubCall(void){  
	switch (uip_udp_conn->lport)  {  
		case (HTONS(PORT_NTPD)):  
			NtpDCall((ntpMsg *)uip_appdata, uip_datalen());  
		break;  
		case (HTONS(PORT_SUBD)):  
			subDCall((subMsg *)uip_appdata, uip_datalen());  
		break;  
	}    
}   
void uip_UdpAppHubInit(void){  
	NtpDInit();
	subDInit();
}  

