.PHONY: all clean

all:
	gcc -Wall -o /tmp/test ./hoge.c -lhinawa `pkg-config --cflags --libs libhinawa`

clean:
	rm /tmp/test
