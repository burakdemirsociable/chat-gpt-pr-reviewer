# Apache License
# Version 2.0, January 2004
# Author: Eugene Tkachenko

import os
from git import Git 
from pathlib import Path
from ai_files.chat_gpt import ChatGPT
from ai_files.ai_bot import AiBot
from log import Log
from env_vars import EnvVars
from repository.github import GitHub
from repository.repository import RepositoryError

separator = "\n\n----------------------------------------------------------------------\n\n"
log_file = open('output.txt', 'a')

def main():
    vars = EnvVars()
    vars.check_vars()

    ai = ChatGPT(vars.chat_gpt_token, vars.chat_gpt_model)
    github = GitHub(vars.token, vars.owner, vars.repo, vars.pull_number)

    remote_name = Git.get_remote_name()

    Log.print_green("Remote is", remote_name)
    changed_files = Git.get_diff_files(remote_name=remote_name, head_ref=vars.head_ref, base_ref=vars.base_ref)
    Log.print_green("Found changes in files", changed_files)

    if len(changed_files) == 0:
        Log.print_red("No changes between branches")

    for file in changed_files:
        Log.print_green("Checking file", file)

        _, file_extension = os.path.splitext(file)
        file_extension = file_extension.lstrip('.')
        if file_extension not in vars.target_extensions:
            Log.print_yellow(f"Skipping unsupported extension {file_extension} for file {file}")
            continue

        file_diffs = Git.get_diff_in_file(remote_name=remote_name, head_ref=vars.head_ref, base_ref=vars.base_ref,
                                          file_path=file)
        if not file_diffs:  # Assuming get_diff_in_file now returns None or empty list if no diffs
            Log.print_red("No diffs found in the file")
            continue

        Log.print_green(f"Asking AI. Diff Len: {len(file_diffs)}")
        response = ai.ai_request_diffs(diffs=file_diffs)  # Adjusted to send only diffs

        log_file.write(f"{separator}{file_diffs}{separator}{response}{separator}")

        if AiBot.is_no_issues_text(response):
            Log.print_green("File looks good. Continue", file)
        else:
            responses = AiBot.split_ai_response(response)
            if not responses:
                Log.print_red("Responses were not parsed correctly:", responses)

            result = False
            for response in responses:
                if response.line:
                    result = post_line_comment(github=github, file=file, text=response.text, line=response.line)
                if not result:
                    result = post_general_comment(github=github, file=file, text=response.text)
                if not result:
                    raise RepositoryError("Failed to post any comments.")


def post_line_comment(github: GitHub, file: str, text:str, line: int):
    Log.print_green("Posting line", file, line, text)
    try:
        git_response = github.post_comment_to_line(
            text=text, 
            commit_id=Git.get_last_commit_sha(file=file), 
            file_path=file, 
            line=line,
        )
        Log.print_yellow("Posted", git_response)
        return True
    except RepositoryError as e:
        Log.print_red("Failed line comment", e)
        return False

def post_general_comment(github: GitHub, file: str, text:str) -> bool:
    Log.print_green("Posting general", file, text)
    try:
        message = f"{file}\n{text}"
        git_response = github.post_comment_general(message)
        Log.print_yellow("Posted general", git_response)
        return True
    except RepositoryError:
        Log.print_red("Failed general comment")
        return False

if __name__ == "__main__":
    main()

log_file.close()