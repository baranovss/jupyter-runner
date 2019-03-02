import logging
import shlex
import os
from os.path import basename, splitext, exists, join, abspath, samefile
import subprocess


LOG_FORMAT = '[%(asctime)s %(levelname)s] %(message)s'
LOGGER = logging.getLogger(__file__)


def get_tasks(
        parameter_file,
        notebooks,
        output_dir,
        debug,
        overwrite,
        output_format,
        timeout,
        allow_errors
):
    """Return list of tasks to run based on parameters and notebooks.

    The number of tasks returned is the product of:
        Number of parameters x Number of notebooks.

    :param notebooks: List of notebook files to execute.
    :param parameter_file: Path to a parameter file. Can be None.
    :param output_dir: Output directory to store results.
    :param debug: Boolean enabling debug notebook execution.
    :param overwrite: Boolean enabling overwriting output
    :param output_format: String 'html' or 'ipynb'
    :param timeout: Timeout in seconds. -1 means infinite.
    :param allow_errors: Boolean authorizing errors in notebook execution.
    :return List of **kwargs to pass to execute_notebook
    """
    # pylint: disable=too-many-locals
    parameters = _parse_parameter_file(parameter_file)

    tasks = []
    for param_id, params in enumerate(parameters):
        for notebook in notebooks:
            if parameter_file is None:
                file_suffix = ''
            elif 'JUPYTER_OUTPUT_SUFFIX' in params:
                file_suffix = '_%s' % params['JUPYTER_OUTPUT_SUFFIX']
            else:
                file_suffix = '_%d' % (param_id + 1)
            extension = '.%s' % output_format \
                if output_format != 'notebook' else '.ipynb'
            output_name = '%s%s%s' % (splitext(basename(notebook))[0],
                                      file_suffix,
                                      extension)
            output_file = abspath(join(output_dir, output_name))
            tasks.append(
                dict(
                    notebook=notebook,
                    params=params,
                    output_file=output_file,
                    debug=debug,
                    overwrite=overwrite,
                    output_format=output_format,
                    timeout=timeout,
                    allow_errors=allow_errors,
                )
            )

    for task_id, task in enumerate(tasks):
        LOGGER.debug('Task %d: %s', task_id + 1, task)

    return tasks


def execute_notebook(
        notebook_file,
        parameters,
        output_file,
        debug,
        overwrite,
        output_format,
        timeout,
        allow_errors
):
    """
    Execute notebook and export output result file.

    :param notebook_file: Notebook file to execute.
    :param parameters: Dictionary of environment variables.
    :param output_file: Output HTML file path.
    :param debug: Boolean enabling debug notebook execution.
    :param overwrite: Boolean enabling overwriting output
    :param output_format: String 'html' or 'ipynb'
    :param timeout: Timeout in seconds
    :param allow_errors: Boolean authorizing errors in notebook execution
    """
    in_place = False
    if exists(output_file):
        if not overwrite:
            LOGGER.info("Skip existing output file %s", output_file)
            return 0

        if samefile(notebook_file, output_file):
            LOGGER.debug("Executing notebook %s in place", output_file)
            in_place = True
        else:
            LOGGER.info("Remove existing output file %s", output_file)
            os.remove(output_file)

    cmd = ['jupyter', 'nbconvert', '--execute',
           '--ExecutePreprocessor.timeout=%s' % timeout,
           '--output', output_file,
           '--to', output_format]
    if debug:
        cmd.append('--debug')
    if in_place:
        cmd.append('--inplace')
    if allow_errors:
        cmd.append('--allow-errors')
    cmd.append(notebook_file)
    env = os.environ.update(parameters)

    LOGGER.info("Executing command: %s with parameters: %s",
                ' '.join(cmd), str(parameters))
    ret = subprocess.call(cmd, env=env)

    return ret


def _parse_parameters(text):
    """
    Return environment dictionary from text.

    VAR1=VAL1 VAR2=VAL2 VAR3=VAL3
    returns
    {'VAR1': 'VAL1 with spaces', 'VAR2': 'VAL2', 'VAR3': 'VAL3'}
    :param text: Environment text string in bash format.
    :return: parameters dictionary to pass to subprocess as environment
    """
    tokens = shlex.shlex(text, posix=True)
    is_key = True
    current_key = None
    environ = {}

    for token in tokens:
        if token == '=':
            is_key = not is_key
            continue

        if is_key:
            current_key = token
        else:
            environ[current_key] = token
            is_key = True

    return environ


def _parse_parameter_file(filename):
    """
    Open filename and return the parameters as list of dictionaries.

    :param filename: Filename containing one set of parameters per line.
    :return: dict of parameters
    """
    if filename is None:
        # Return list of one parameter
        return [{}]
    with open(filename) as file_obj:
        lines = file_obj.readlines()

    parameters = []
    for line in lines:
        parameters.append(_parse_parameters(line))

    return parameters
