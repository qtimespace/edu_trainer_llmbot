#!/bin/sh
# Учебный пароль student — из окружения контейнера (выдаёт тренажёр), sshd — только на 127.0.0.1.
set -e
if [ -n "$LESSON_PASSWORD" ]; then
    echo "student:$LESSON_PASSWORD" | chpasswd
fi
# том /home мог прийти пустым после пересоздания — вернуть хозяев папок
chown -R lobby:lobby /home/lobby 2>/dev/null || true
chown -R student:student /home/student 2>/dev/null || true
mkdir -p /run/sshd
/usr/sbin/sshd
exec sleep infinity
