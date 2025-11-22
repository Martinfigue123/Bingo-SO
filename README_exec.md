Instrucciones para ejecutar el codigo:
1. Ejecutar el codigo server.py [MAX_JUGADORES] (opcional, si se omite, el número máximo por defecto es 3)
2. En otra terminal ejecutar el codigo client.py junto con cuatro argumentos (moderador): [HOST] [PORT] [NICKNAME] mod
3. En una tercera terminal volver a ejecutar client.py con tres argumentos: [HOST] [PORT] [NICKNAME]
4. Se pueden ejecutar tantos client.py como el máximo que permite el server.
5. Ejecutar en el terminal del moderador comando 'start'. (Si el servidor se llena, empieza el juego automáticamente).

Importante, gana el jugador al completar una fila, columna o una diagonal (de esquina superior a esquina inferior).


Características modificadas del protocolo original del informe.
- Decidimos incluir al moderador como jugador, debido a que utilizaba una terminal que queda inutilizado tras iniciar una partida, ya que lo que pretendíamos que el moderador hacía lo hace el servidor. De esta forma la terminal del moderador también es jugador y se pueden usar mejor los recursos.
