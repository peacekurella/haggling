from Net.BaseModels.SequenceEncoder import SequenceEncoder
from Net.BaseModels.SequenceDecoder import SequenceDecoder
import tensorflow as tf
import os
import sys

# configuration changes for RTX enabled devices
physical_devices = tf.config.list_physical_devices('GPU')
tf.config.experimental.set_memory_growth(physical_devices[0], enable=True)


class ConcatenationEncoderDecoderMSE:
    """
    Concatenated state input, sequence reconstruction using MSE loss
    """

    def __init__(self, enc_units, batch_size, enc_layers, enc_dropout_rate,
                 dec_units, output_size, dec_layers, dec_dropout_rate,
                 learning_rate, auto_encoder_dir):
        """
        Initializes the AutoEncoder class with MSE loss
        :param enc_units: Number of hidden units in encoder
        :param batch_size: Batch size for training
        :param enc_layers: Number of layers in the Encoder
        :param enc_dropout_rate: Encoder Dropout rate
        :param dec_units: Number of hidden units in Decoder
        :param output_size: Number of output key points
        :param dec_layers: Number of layers in the Decoder
        :param dec_dropout_rate: Decoder Dropout rate
        :param auto_encoder_dir: checkpoint_dir for auto_encoder
        :param learning_rate: learning rate
        """

        # create encoder
        self.encoder = SequenceEncoder(
            enc_units,
            batch_size,
            enc_layers,
            enc_dropout_rate
        )

        # create decoder
        self.decoder = SequenceDecoder(output_size, dec_units, batch_size, dec_layers, dec_dropout_rate, True)

        # create optimizer
        self.optimizer = tf.keras.optimizers.Adam(
            lr=learning_rate
        )

        # create checkpoint saver
        self.checkpoint = tf.train.Checkpoint(
            optimizer=self.optimizer,
            encoder=self.encoder,
            decoder=self.decoder
        )

        # load the decoder from auto encoder
        auto_encoder = tf.train.Checkpoint(
            decoder=self.decoder
        )

        try:
            auto_encoder.restore(
                tf.train.latest_checkpoint(auto_encoder_dir)
            ).expect_partial()
        except:
            print("Loading decoder failed")
            sys.exit(0)

    def save_model(self, checkpoint_dir):
        """
        Saves the model checkpoint
        :param checkpoint_dir: Directory to save the checkpoint in
        :return:
        """
        ckpt_prefix = os.path.join(checkpoint_dir, "ckpt")
        self.checkpoint.save(ckpt_prefix)

    def load_model(self, checkpoint_dir):
        """
        Loads the model from the checkpoint
        :param checkpoint_dir: Directory in which the checkpoint is stored
        :return:
        """
        self.checkpoint.restore(
            tf.train.latest_checkpoint(checkpoint_dir)
        )

    @tf.function
    def train_step(self, input_seq, target_seq):
        """
        Defines a backward pass through the network
        :param input_seq:
        :param target_seq:
        :return:
        """

        # initialize loss
        loss = 0
        time_steps = target_seq.shape[1]

        # initialize encoder hidden state
        enc_hidden = self.encoder.initialize_hidden_state(self.encoder.batch_size)

        with tf.GradientTape() as tape:
            # pass through encoder
            enc_output, enc_hidden = self.encoder(input_seq, enc_hidden, True)

            # input the hidden state
            dec_hidden = enc_hidden
            dec_input = tf.zeros(target_seq[:, 0].shape)

            # start teacher forcing the network
            for t in range(time_steps):
                # pass dec_input and target sequence to decoder
                prediction, dec_hidden, _ = self.decoder(dec_input, dec_hidden, enc_output, True)

                # calculate the loss for every time step
                losses = tf.keras.losses.MSE(target_seq[:, t], prediction)
                loss += tf.reduce_mean(losses)

                # purge the tensors from memory
                del dec_input, prediction

                # set the next target value as input to decoder
                dec_input = target_seq[:, t]

        # calculate average batch loss
        batch_loss = (loss / time_steps)

        # get trainable variables
        variables = self.encoder.trainable_variables

        # get the gradients
        gradients = tape.gradient(loss, variables)

        # purge tape from memory
        del tape

        # apply gradients to variables
        self.optimizer.apply_gradients(zip(gradients, variables))

        loss_dict = {
            'CEDM':
                {
                    'Reconstruction Loss': batch_loss
                }
        }

        return loss_dict

    def run_inference(self, input_seq, time_steps, output_shape):
        """
        Returns the predictions given input_seq
        :param output_shape: shape of the decoder output
        :param time_steps: Number of time steps to run the inference operation for
        :param input_seq: encoder input sequence
        :return: predictions tensor of shape (batch_size, seqLength, input_size)
        """

        # initialize encoder hidden state
        enc_hidden = self.encoder.initialize_hidden_state(self.encoder.batch_size)

        # encoder output
        enc_output, enc_hidden = self.encoder(input_seq, enc_hidden, False)

        # set the decoder hidden state and input
        dec_input = tf.zeros(output_shape)
        dec_hidden = enc_hidden

        # list of predictions
        predictions = []

        for t in range(time_steps):
            # get the predictions
            prediction, dec_hidden, _ = self.decoder(dec_input, dec_hidden, enc_output, False)
            predictions.append(tf.expand_dims(prediction, axis=1))

            # update inputs to decoder
            del dec_input
            dec_input = prediction

        return tf.concat(predictions, axis=1)