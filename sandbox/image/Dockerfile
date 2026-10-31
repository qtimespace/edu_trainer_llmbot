# Песочница ученика: Linux с bash, git, python3 и ssh. Терминал браузера входит как lobby,
# ученик сам подключается: ssh student@lab (учебный пароль задаёт entrypoint из LESSON_PASSWORD).
FROM debian:bookworm-slim

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        bash coreutils nano vim-tiny less procps curl ca-certificates git python3 \
        openssh-client openssh-server sshpass iputils-ping tree file man-db \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash lobby \
    && useradd -m -s /bin/bash student \
    && mkdir -p /run/sshd

COPY sshd_config /etc/ssh/sshd_config.d/trainer.conf
COPY history.sh /etc/profile.d/trainer-history.sh
COPY motd /etc/motd
COPY lobby_profile /home/lobby/.bash_profile
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh \
    && cat /etc/profile.d/trainer-history.sh >> /etc/bash.bashrc \
    && chown lobby:lobby /home/lobby/.bash_profile \
    && ssh-keygen -A

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
