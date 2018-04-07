# UDP Reliable Simulation
A Python implementation of Go-Back-N and Selective Repeat protocols for UDP sockets.

## Requirements
Just Python3 and nothing else

## Input File Format
The input file GBN.txt / SR.txt are the input configuration files for the program. The format is as follows:
1. Protocol Name: GBN or SR
2. m N; where m = no of bits used in sequence numbers, N = Window size
3. Timeout period in milliseconds
4. Size of the segment in bytes

## Server Execution
Run the `server.py` file using a terminal or command prompt passing input file and port number as arguments. A sample command is as follows:
`python3 server.py GBN.txt 1024`

## Client Execution
Run the `client.py` file using a terminal or command prompt passing input file and server port number as arguments. A sample command is as follows:
`python3 client.py GBN.txt 1024`
