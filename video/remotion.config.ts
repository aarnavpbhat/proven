import { Config } from '@remotion/cli/config';

Config.setVideoImageFormat('jpeg');
Config.setCodec('h264');
Config.setOverwriteOutput(true);
// One frame at a time by default: a model-training job shares this 24 GB machine.
Config.setConcurrency(1);
