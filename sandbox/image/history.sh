# История команд пишется сразу — агент-проверяющий видит, что ученик делал.
export HISTTIMEFORMAT='%F %T '
export HISTSIZE=5000
export HISTFILESIZE=10000
shopt -s histappend 2>/dev/null
case "$PROMPT_COMMAND" in *"history -a"*) ;; *) PROMPT_COMMAND="history -a${PROMPT_COMMAND:+; $PROMPT_COMMAND}" ;; esac
