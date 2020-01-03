def plumbum_msg(command_exit):
    return "Exit code %d.\nCommand output:\n%s.\nError msg:\n%s\n" % (
        command_exit[0],
        command_exit[1],
        command_exit[2],
    )


def git_check(ret):
    assert ret[0] == 0, "Error returned by git.\n" + plumbum_msg(ret)
    return ret
