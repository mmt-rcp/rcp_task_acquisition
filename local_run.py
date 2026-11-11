import multiprocessing

# for running through IDE so theres no import collisions
if __name__ == "__main__":
    # set the most early the multiprocess start method to spawn:
    multiprocessing.set_start_method("spawn", force=True)
    from rcp_task_acquisition.__main__ import run_app

    run_app()
