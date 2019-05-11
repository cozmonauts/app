#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

import asyncio
import json
import os
import sys
from abc import abstractmethod, ABC
from enum import Enum
from functools import reduce
from typing import List

import cozmo
from pkg_resources import resource_filename

from cozmonaut.operation.interact.service import Service

# The conversation data directory
_data_directory = resource_filename(__name__, 'data')


class ConversationRoles(Enum):
    """
    A set of roles in a conversation.
    """

    a = 1
    b = 2
    both = 3


class ConversationAction(ABC):
    """
    An abstract conversation action.
    """

    @abstractmethod
    async def perform(self, robot_a: cozmo.robot.Robot, robot_b: cozmo.robot.Robot):
        """
        Perform the action.

        :param robot_a: The robot A instance
        :param robot_b: The robot B instance
        """


class ConversationActionGroup(ConversationAction):
    """
    A conversation action for running sub-actions simultaneously.
    """

    def __init__(self, subs: List[ConversationAction]):
        """
        Initialize a group action.

        :param subs: The sub-actions
        """

        self._subs = subs

    async def perform(self, robot_a: cozmo.robot.Robot, robot_b: cozmo.robot.Robot):
        """
        Perform the action by running its sub-actions simultaneously.

        :param robot_a: The robot A instance
        :param robot_b: The robot B instance
        """

        # The coroutines to run
        coros = []

        # Fire off each sub-action simultaneously
        for action in self._subs:
            coros.append(action.perform(robot_a, robot_b))

        # Wait for coroutines to complete
        await asyncio.gather(*coros)


class ConversationActionSayText(ConversationAction):
    """
    A conversation action for saying text.
    """

    def __init__(self, roles: ConversationRoles, text: str, duration: float, pitch: float, human: bool):
        """
        Initialize a say text action.

        :param roles: The conversation roles
        :param text: The text to say
        :param duration: The duration multiplier
        :param pitch: The pitch multiplier
        :param human: Whether or not to use an unprocessed human voice
        """

        self._roles = roles
        self._text = text
        self._duration = duration
        self._pitch = pitch
        self._human = human

    async def perform(self, robot_a: cozmo.robot.Robot, robot_b: cozmo.robot.Robot):
        """
        Perform the action by saying text.

        :param robot_a: The robot A instance
        :param robot_b: The robot B instance
        """

        # The robots taking part
        robots = []
        if self._roles == ConversationRoles.a:
            robots.append(robot_a)
        elif self._roles == ConversationRoles.b:
            robots.append(robot_b)
        elif self._roles == ConversationRoles.both:
            robots.append(robot_a)
            robots.append(robot_b)

        # The coroutines to run
        coros = []

        # Say the text simultaneously on each robot taking part
        for robot in robots:
            coros.append(robot.say_text(
                text=self._text,
                use_cozmo_voice=not self._human,
                duration_scalar=self._duration,
                voice_pitch=self._pitch,
            ).wait_for_completed())

        # Wait for coroutines to complete
        await asyncio.gather(*coros)


class ConversationActionAnimTrigger(ConversationAction):
    """
    A conversation action for playing an animation trigger.
    """

    def __init__(self, roles: ConversationRoles, trigger: cozmo.anim.AnimationTrigger):
        """
        Initialize an animation trigger action.

        :param roles: The conversation roles
        :param trigger: The animation trigger
        """

        self._roles = roles
        self._trigger = trigger

    async def perform(self, robot_a: cozmo.robot.Robot, robot_b: cozmo.robot.Robot):
        """
        Perform the action by playing the trigger.

        :param robot_a: The robot A instance
        :param robot_b: The robot B instance
        """

        # The robots taking part
        robots = []
        if self._roles == ConversationRoles.a:
            robots.append(robot_a)
        elif self._roles == ConversationRoles.b:
            robots.append(robot_b)
        elif self._roles == ConversationRoles.both:
            robots.append(robot_a)
            robots.append(robot_b)

        # The coroutines to run
        coros = []

        # Play the trigger simultaneously on each robot taking part
        for robot in robots:
            coros.append(robot.play_anim_trigger(self._trigger).wait_for_completed())

        # Wait for coroutines to complete
        await asyncio.gather(*coros)


class Conversation:
    """
    A conversation between two robots.

    Conversations are two-sided, but it is possible to perform just one side of
    a conversation for testing purposes.
    """

    # The conversation actions
    actions = []

    async def perform(self, robot_a: cozmo.robot.Robot, robot_b: cozmo.robot.Robot):
        """
        Perform the conversation with robots.

        :param robot_a: The robot A instance
        :param robot_b: The robot B instance
        """

        # Perform each action in sequence
        for action in self.actions:
            await action.perform(
                robot_a=robot_a,
                robot_b=robot_b,
            )


class ServiceConvo(Service):
    """
    The Convo service manages conversations.
    """

    def __init__(self):
        super().__init__()

    def start(self):
        """
        Start the Convo service.
        """

        super().start()

    def stop(self):
        """
        Stop the Convo service.
        """

        super().stop()

    @staticmethod
    def list() -> List[str]:
        """
        Retrieve a summary of all available conversations.

        :return: A list of names of known conversations
        """

        # List all files in the conversation directory
        return [file[:-5] for file in os.listdir(_data_directory)
                if os.path.isfile(os.path.join(_data_directory, file)) and file.endswith('.json')]

    def load(self, name: str) -> Conversation:
        """
        Load a conversation by name.

        :param name: The conversation name
        :return: The conversation
        """

        # Create the target file name for the conversation
        filename = os.path.join(_data_directory, f'{name}.json')

        # Open the conversation file
        with open(filename) as file:
            # Load conversation data
            data = json.load(file)

            # Sanity check name of conversation
            if not data.get('name') == name:
                raise RuntimeError('conversation name mismatch')

            # The loaded conversation
            convo = Conversation()

            # Load each action in the script
            for action in data.get('script', []):
                convo.actions.append(self._load_action(action))

            return convo

    def _load_action(self, data):
        """
        Load an action.

        :param data: The source data
        """

        # Get the action type
        action_type = data.get('action')

        if action_type == 'say':
            return self._load_action_say(data)
        elif action_type == 'trigger':
            return self._load_action_trigger(data)
        elif action_type == 'group':
            return self._load_action_group(data)

    def _load_action_say(self, data):
        """
        Load a say text action.

        :param data: The source data
        """

        # The "who" parameter (required)
        # This is the name of the speaker
        param_who: str = data['who']

        # The "what" parameter (required)
        # This is the text to say
        param_what: str = data['what']

        # The "speed" parameter (optional)
        # This is a multiplier on the duration
        param_speed: float = data.get('speed', 1)  # Default to 1

        # The "pitch" parameter (optional)
        # This is a multiplier on the pitch
        param_pitch: float = data.get('pitch', 1)  # Default to 1

        # The "human" parameter (optional)
        # This tells whether to disable Cozmo's typical voice processing
        # When this is True, you get a creepy male human voice instead
        param_human: bool = data.get('human', False)  # Default to False

        # Create the say text action
        return ConversationActionSayText(
            roles=self._get_roles(param_who),
            text=param_what,
            duration=param_speed,
            pitch=param_pitch,
            human=param_human,
        )

    def _load_action_trigger(self, data):
        """
        Load an animation trigger action.

        :param data: The source data
        """

        # The "who" parameter (required)
        # This is the name of the speaker
        param_who = data['who']

        # The "what" parameter (required)
        # This animation trigger to perform
        param_what = data['what']

        # Look up the requested animation trigger class
        trigger: cozmo.anim.AnimationTrigger = self._find_attr(param_what)

        # Create the animation trigger action
        return ConversationActionAnimTrigger(
            roles=self._get_roles(param_who),
            trigger=trigger,
        )

    def _load_action_group(self, data):
        """
        Load a group of simultaneous actions.

        :param data: The source data
        """

        # The "what" parameter (required)
        # This is the list of sub-actions to perform
        param_what: List = data['what']

        # The loaded sub-actions
        subs = []

        # Load each sub-action
        for sub_data in param_what:
            subs.append(self._load_action(sub_data))

        # Create the group action
        return ConversationActionGroup(subs)

    @staticmethod
    def _get_roles(who: str):
        """
        Get the roles pertaining to a "who" string.

        :param who: The "who" string
        :return: The conversation roles
        """

        if who == 'a' or who == 'A' or str(who) == '1':
            return ConversationRoles.a
        elif who == 'b' or who == 'B' or str(who) == '2':
            return ConversationRoles.b
        elif who == 'both' or who == 'BOTH' or who == 'ab':
            return ConversationRoles.both

    @staticmethod
    def _find_attr(name):
        """
        Look up a Python attribute by dotted name.

        We use this to find animation trigger classes.

        :param name: The dotted name
        :return: The attribute value
        """

        return reduce(getattr, name.split("."), sys.modules[__name__])
