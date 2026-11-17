# Песочница ученика: Linux с bash, vim, nano, git, python3, node/npm и ssh. Терминал браузера входит как lobby,
# ученик сам подключается: ssh student@lab (учебный пароль задаёт entrypoint из LESSON_PASSWORD).
FROM debian:bookworm-slim

# Кириллица в терминале: без UTF-8 Backspace стирает полбуквы (в файл уходит битый байт), ls показывает русские
# имена кодами. ENV — для терминала lobby и проверок, /etc/default/locale — для ssh-сессий на lab (pam_env).
ENV LANG=C.UTF-8

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        bash coreutils nano vim less procps curl ca-certificates git python3 nodejs npm \
        openssh-client openssh-server sshpass iputils-ping iproute2 tree file man-db \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash lobby \
    && useradd -m -s /bin/bash student \
    && mkdir -p /run/sshd \
    && echo 'LANG=C.UTF-8' > /etc/default/locale

COPY sshd_config /etc/ssh/sshd_config.d/trainer.conf
COPY history.sh /etc/profile.d/trainer-history.sh
COPY motd /etc/motd
COPY lobby_profile /etc/trainer-skel/lobby.bash_profile
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh \
    && cat /etc/profile.d/trainer-history.sh >> /etc/bash.bashrc \
    && chmod 0644 /etc/trainer-skel/lobby.bash_profile \
    && ssh-keygen -A

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
