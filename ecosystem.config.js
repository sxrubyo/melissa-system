module.exports = {
  apps: [
    {
      name: "melissa",
      script: "/home/ubuntu/melissa/run.sh",
      cwd: "/home/ubuntu/melissa",
      restart_delay: 3000,
      max_restarts: 10,
      out_file: "/home/ubuntu/melissa/logs/melissa.log",
      error_file: "/home/ubuntu/melissa/logs/melissa-error.log",
      watch: false,
    },
    {
      name: "melissa-clinica-de-las-americas",
      script: "/home/ubuntu/melissa-instances/clinica-de-las-americas/run.sh",
      cwd: "/home/ubuntu/melissa-instances/clinica-de-las-americas",
      restart_delay: 3000,
      max_restarts: 10,
      out_file: "/home/ubuntu/melissa-instances/clinica-de-las-americas/logs/melissa.log",
      error_file: "/home/ubuntu/melissa-instances/clinica-de-las-americas/logs/error.log",
      watch: false,
    }
  ]
}
