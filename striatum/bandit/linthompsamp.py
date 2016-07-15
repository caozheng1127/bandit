import logging
import math

from striatum.bandit.bandit import BaseBandit

import numpy as np

LOGGER = logging.getLogger(__name__)


class LinThompSamp (BaseBandit):

    def __init__(self, actions, storage, d=6, delta=0.5, R=0.5, epsilon=0.1):
        super(LinThompSamp, self).__init__(storage, actions)

        self.last_history_id = -1
        self.linthompsamp_ = None
        self.d = d

        # 0 < delta <= 1
        if not isinstance(delta, float):
            raise ValueError("delta should be float")
        elif (delta < 0) or (delta > 1):
            raise ValueError("delta should be in (0, 1]")
        else:
            self.delta = delta

        # R > 0
        if not isinstance(R, float):
            raise ValueError("R should be float")
        elif R <= 0:
            raise ValueError("R should be positive")
        else:
            self.R = R

        # 0 < epsilon < 1
        if not isinstance(epsilon, float):
            raise ValueError("epsilon should be float")
        elif (epsilon < 0) or (epsilon > 1):
            raise ValueError("epsilon should be in (0, 1)")
        else:
            self.epsilon = epsilon

        # model initialization
        self.t = 0
        v = 0
        B = np.identity(self.d)
        muhat = np.zeros(self.d)
        f = np.zeros(self.d)
        self._ModelStorage.save_model({'B': B, 'muhat': muhat, 'f': f})

    def linthompsamp(self):

        while True:
            context = yield
            self.t += 1
            B = self._ModelStorage.get_model()['B']
            muhat = self._ModelStorage.get_model()['muhat']
            v = self.R * np.sqrt(24 / self.epsilon * self.d * np.log(self.t / self.delta))
            mu = np.random.multivariate_normal(muhat, v**2 * np.linalg.inv(B), self.d)
            action_max = self._actions[np.argmax(np.dot(np.array(context), np.array(mu)))]
            yield action_max
        raise StopIteration


    def get_action(self, context):
        """Return the action to perform
        Parameters
        ----------
        context : {array-like, None}
            The context of current state, None if no context avaliable.
        Returns
        -------
        history_id : int
            The history id of the action.
        action : Actions object
            The action to perform.
        """
        if self.linthompsamp_ is None:
            self.linthompsamp_ = self.linthompsamp()
            action_max = self.linthompsamp_.next()
        else:
            action_max = self.linthompsamp_.send(context)

        self.last_history_id = self.last_history_id + 1
        self._HistoryStorage.add_history(np.transpose(np.array([context])), action_max, reward=None)
        return self.last_history_id, action_max

    def reward(self, history_id, reward):
        """Reward the preivous action with reward.
        Parameters
        ----------
        history_id : int
            The history id of the action to reward.
        reward : float
            A float representing the feedback given to the action, the higher
            the better.
        """
        if history_id != self.last_history_id:
            raise ValueError("The history_id should be the same as last one.")

        if not isinstance(reward, float):
            raise ValueError("reward should be a float.")

        if reward > 1. or reward < 0.:
            LOGGER.warning("reward passing in should be between 0 and 1"
                           "to maintain theoratical guarantee.")

        context = self._HistoryStorage.unrewarded_histories[history_id].context
        reward_action = self._HistoryStorage.unrewarded_histories[history_id].action

        # Update the model
        B = self._ModelStorage.get_model()['B']
        muhat = self._ModelStorage.get_model()['muhat']
        f = self._ModelStorage.get_model()['f']
        B += np.dot(context, context)
        f += reward * context
        muhat = np.linalg.inv(B) * f
        self._ModelStorage.save_model({'B': B, 'muhat': muhat, 'f': f})

        # Update the history
        self._HistoryStorage.add_reward(history_id, reward)
