#!/bin/sh
# Учебный пароль student — из окружения контейнера (выдаёт тренажёр), sshd — только на 127.0.0.1.
set -e
if [ -n "$LESSON_PASSWORD" ]; then
    echo "student:$LESSON_PASSWORD" | chpasswd
fi
# /home — том места ученика (после пересоздания пустой): домашние папки создаём сами
for u in lobby student; do
    if [ ! -d "/home/$u" ]; then
        mkdir -p "/home/$u"
        cp -a /etc/skel/. "/home/$u/"
        [ -f "/etc/trainer-skel/$u.bash_profile" ] && cp "/etc/trainer-skel/$u.bash_profile" "/home/$u/.bash_profile"
    fi
    chown -R "$u:$u" "/home/$u" 2>/dev/null || true
    chmod 0750 "/home/$u"
done
rm -rf /home/lost+found 2>/dev/null || true
mkdir -p /run/sshd
/usr/sbin/sshd
exec sleep infinity
